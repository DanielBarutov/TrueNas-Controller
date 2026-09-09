# План 41. Надёжность publish: идемпотентность, retry и восстановление

## Цель

Устранить найденные независимым ревью сценарии, в которых повтор HTTP-запроса,
доставка сообщения дважды, падение worker между TrueNAS и commit либо два
параллельных задания могут:

- подключить двум станциям один writable clone;
- потерять исходный mapping и сделать rollback недостоверным;
- повторить TrueNAS write после неизвестного результата;
- продолжить switch по устаревшему preflight;
- оставить job навсегда в `publishing`;
- удалить dataset по устаревшему состоянию;
- сделать enrollment невосстановимым после потери HTTP-ответа.

План закрывает весь путь `HTTP -> DB/outbox -> worker -> TrueNAS -> agent -> UI`.
Реальные TrueNAS write/delete операции не входят в локальную реализацию и
остаются отдельными согласованными smoke gates.

## Входы и зависимости

- требования разделов 5, 6, 8 и 9 `CODEX.md`;
- текущие планы 21, 25, 26, 33, 36, 38, 39 и 40;
- `publish_jobs`, `publish_targets`, `publish_artifacts`, `outbox_events`;
- Dramatiq/Redis worker и TrueNAS JSON-RPC adapter;
- heartbeat, command delivery и native/legacy Windows agents;
- PostgreSQL как обязательный concurrency target; SQLite остаётся локальным
  функциональным профилем.

## Подтверждённые дефекты

1. Clone path зависит от изменяемого `display_name`; две станции с одинаковым
   именем получают одинаковый destination, а переименование меняет результат
   повтора того же job.
2. Mapping проверяется по станции, но не как взаимно однозначный набор: один
   target/extent/LUN может пройти для нескольких выбранных станций.
3. Исходный mapping и прогресс сохраняются только после серии TrueNAS writes.
   После падения повтор принимает уже новый mapping за старый.
4. Между разными job нет эксклюзивного claim станции; два worker могут менять
   один extent одновременно.
5. Dispatch доверяет сохранённому preflight, а `allow_hot_switch` не участвует
   в server-side policy. Между prepare и switch состояние ПК может измениться.
6. Verify подтверждает только TrueNAS mapping и не требует нового agent
   snapshot с доступным `D:` после switch.
7. Transport одинаково повторяет read и write JSON-RPC. При потерянном ответе
   snapshot/clone/update/delete могут уже выполниться на NAS.
8. Publish и cleanup actors не имеют безопасного recovery/retry пути;
   необработанная ошибка может оставить job в `publishing`.
9. Повтор создания draft конфликтует из-за нового `correlation_id`, а frontend
   генерирует новый idempotency key на каждую отправку формы.
10. Повтор и конкурентный вызов dispatch не идемпотентны; возможно более одного
    outbox event для одного job.
11. Outbox completion не проверяет владельца/lease token, поэтому старый relay
    может перезаписать результат нового владельца.
12. Cleanup отправляется в Redis без transactional outbox, не claim-ит artifact
    и перед delete не перечитывает актуальный live mapping.
13. Enrollment/bootstrap расходует one-shot token и создаёт server-side secret
    до ответа; потерянный ответ нельзя восстановить.
14. Legacy Python agent может завершить heartbeat loop на неверной подписанной
    команде и повторяет постоянные HTTP 4xx как временный сбой.
15. Heartbeat не имеет идентификатора снимка, поэтому потерянный ответ создаёт
    дубликаты истории.
16. UI ищет `error_code=recovery_required`, хотя recovery задаётся target
    status, а реальные коды имеют другие значения.

## Решения и инварианты

### Идентичность ресурсов и mapping

- Имена нового master snapshot и station clone вычисляются только из полного
  `job_id`, стабильного `station_id` и нормализованного source dataset. Label и
  `display_name` используются только для отображения и аудита.
- Для одного `(job_id, station_id)` существует ровно один planned destination и
  один `publish_artifact`. Повтор job возвращает тот же путь.
- До dispatch и ещё раз до switch весь выбранный набор обязан иметь уникальные
  `target_id`, `target_name`, `target_iqn`, `initiator_iqn`, `extent_id` и
  association/LUN. Любая коллизия блокирует операции для обеих затронутых
  станций с явной диагностикой.
- Для новых/изменяемых station mapping действует DB/application invariant
  уникальности активного `target_name`/`target_iqn`/`initiator_iqn`.
  Существующие дубликаты сначала выявляются read-only audit и не исправляются
  автоматически.
- Старые clone с прежней схемой имён не переименовываются и не удаляются.

### Idempotency HTTP и dispatch

- Идентичность create request — `idempotency_key` плюс канонический бизнес
  payload. `correlation_id` создаётся один раз для первого job и не участвует в
  сравнении повторного запроса.
- Frontend хранит один idempotency key для одной попытки создания draft и
  повторно использует его после timeout/потери ответа. Новый key появляется
  после явного reset либо изменения бизнес payload.
- Race двух create с одним key разрешается unique constraint + повторным
  чтением существующего job; наружу не выходит `IntegrityError`.
- Dispatch сериализуется блокировкой строки job. Повтор для уже принятого job
  возвращает тот же `accepted` result. На `(aggregate_id, event_type)` действует
  unique constraint, поэтому создаётся ровно один `publish.dispatch` event.
- Terminal job не запускается повторно. API возвращает его фактический статус,
  чтобы клиент мог продолжить polling без создания нового задания.

### Claim станции и fencing

- Перед созданием dispatch event все выбранные станции атомарно claim-ятся
  текущим job в стабильном порядке. Одновременно активен только один publish или
  cleanup, способный менять mapping/artifact станции.
- Claim хранится в БД и содержит `station_id`, `job_id`, непрозрачный
  `lease_token`, срок lease и revision/fencing number. Это не долгоживущая
  SQL-транзакция на время сетевых операций.
- Worker продлевает lease между стадиями. Любая запись прогресса и завершение
  claim проверяют `job_id + lease_token + fencing number`; просроченный worker
  не может перезаписать состояние нового владельца.
- Claim освобождается только после terminal state или явного recovery решения.
  Истёкший lease разрешает resume того же job после read-back, но не слепой
  старт другого job поверх неизвестного mapping.

### Durable workflow и unknown outcome

- До первого TrueNAS write атомарно сохраняются неизменяемый execution plan,
  исходный mapping, ожидаемый target/extent/LUN, master snapshot ref,
  destination dataset/device и idempotency data каждой стадии.
- Стадии фиксируются отдельными короткими транзакциями:
  `planned -> in_progress -> applied | retryable_error | recovery_required`.
  Минимальные стадии: master snapshot, station clone, extent switch, TrueNAS
  read-back, post-switch agent verify и artifact activation.
- Повтор worker всегда загружает checkpoint. Уже подтверждённая стадия
  пропускается; исходный mapping никогда не вычисляется повторно из уже
  изменённого extent.
- Job получает явное состояние `recovery_required`, если remote outcome нельзя
  доказать. Worker exception до внешнего эффекта переводится в bounded retry;
  постоянная ошибка — в `failed`/`partial_failure` с сохранённой причиной.
- Terminal outbox/worker failure обновляет job и audit, поэтому `publishing` не
  остаётся бессрочно без объяснения.

### Политика retry для TrueNAS

- Transport автоматически повторяет только read-only методы, connect/auth и
  запросы, для которых доказано отсутствие server-side эффекта.
- Write (`snapshot.create`, `snapshot.clone`, `extent.update`, dataset delete)
  после timeout/EOF получает `unknown outcome`; тот же write нельзя немедленно
  повторять на уровне transport.
- Application stage выполняет operation-specific read-back:
  - желаемое состояние уже достигнуто — сохранить `applied`;
  - исходное состояние доказанно не изменилось — разрешить ограниченный retry;
  - состояние неоднозначно или изменено не нашим планом — сохранить
    `recovery_required`, прекратить следующие writes и показать evidence.
- Для extent switch read-back проверяет target, association, LUN, extent ID,
  старый device и ожидаемый новый device. Для create/delete проверяется точное
  имя объекта и его ожидаемая принадлежность job/station.
- Backoff ограничен, имеет jitter и единый deadline. Счётчик попыток и
  классификация последней ошибки сохраняются в checkpoint.

### Fresh preflight и post-switch verify

- Dispatch заново вычисляет preflight по последним heartbeat, а worker делает
  ещё одну проверку непосредственно перед каждым extent switch.
- `allow_hot_switch=false` требует свежего online snapshot, доступного `D:` и
  отсутствия blocking процессов. Stale/offline/unknown всегда запрещают switch.
- Для `allow_hot_switch=true` вводится отдельное persisted подтверждение
  оператора. Оно может разрешить только явно показанные process blockers;
  отсутствие свежего heartbeat, `D:`, station binding или уникального mapping
  не обходится.
- После switch Controller запрашивает refresh и ждёт snapshot, принятый позже
  момента switch. `VERIFIED` требует одновременно правильный TrueNAS mapping и
  новый agent snapshot с доступным `D:`. Timeout/нет `D:` сохраняет
  `recovery_required` с фактическим mapping, а не ложный success.

### Outbox и worker delivery

- Claim outbox получает уникальный delivery/lease token. `mark_dispatched` и
  `mark_failed` меняют только `pending` event, принадлежащий тому же worker и
  token; stale completion становится no-op/conflict.
- Lease либо продлевается во время медленной отправки, либо его длительность
  гарантированно превышает deadline одного enqueue. Duplicate delivery всё
  равно считается штатной и поглощается idempotent executor.
- Actor получает bounded retry только для классифицированных retryable ошибок.
  Unknown write outcome обрабатывается checkpoint/read-back, а не Dramatiq
  replay вслепую.

### Cleanup

- Ручной и периодический cleanup создают durable cleanup request и outbox event
  в одной DB-транзакции. Повтор одного request не создаёт второй delete.
- Artifact/station claim сериализует cleanup с publish. Непосредственно перед
  delete worker повторно читает live target -> extent -> device и отказывается
  удалять текущий или неоднозначный dataset.
- Потерянный ответ delete разрешается проверкой существования dataset: отсутствие
  означает подтверждённый успех, наличие — допустимый retry, ошибка чтения —
  `recovery_required`.
- Ошибка постановки периодического cleanup перехватывается, логируется без
  секретов и получает bounded backoff; runtime loop продолжает работу.

### Enrollment и agent delivery

- Новый enrollment protocol использует созданный агентом credential и
  стабильный `enrollment_request_id`. Агент защищённо сохраняет pending
  credential до запроса, сервер хранит только hash.
- Повтор того же request после расходования token возвращает подтверждение того
  же binding, если station/agent/request/credential hash совпадают. Другой
  payload остаётся конфликтом. Raw credential сервер повторно не выдаёт.
- Старый protocol остаётся совместимым на время обновления native agent; уже
  выданные credentials не ротируются автоматически.
- Heartbeat получает `snapshot_id`; уникальность `(station_id, snapshot_id)`
  поглощает повтор после потерянного ответа без второй строки истории.
- Legacy Python agent изолирует ошибочную/невалидную command envelope от
  heartbeat loop. Retry выполняется для timeout/connection/429/5xx; 401/403
  переводят агент в диагностируемое состояние re-enrollment, остальные
  постоянные 4xx не повторяются бесконечно.

### UI и диагностика

- Recovery banner определяется по `target.status=recovery_required`; error code
  отображается как причина, а не как статус.
- UI показывает checkpoint/stage, число попыток, время последнего действия,
  old/desired/observed mapping и следующий безопасный шаг оператора.
- Кнопка «Повторить» продолжает тот же job/request. Новый job создаётся только
  явным действием оператора.
- Текущий принятый default `dry_run=false` сохраняется. Устаревшие формулировки
  `CODEX.md`/`plans/README.md` о другом default приводятся к этому решению до
  изменения кода.

## Последовательность реализации

### 41.1. Стабильные имена и mapping invariants

- [ ] Ввести детерминированный naming по полным UUID и collision tests.
- [ ] Добавить batch uniqueness validation для target/extent/LUN.
- [ ] Добавить read-only audit существующих station mappings и additive DB
  constraints после явного устранения конфликтов.
- [ ] Запретить автоматическое переименование/удаление legacy artifacts.

**Gate:** одинаковые display name и rename между повторами не меняют destination;
две станции не могут пройти с одним writable mapping.

### 41.2. HTTP/dispatch idempotency, station claim и outbox fencing

- [ ] Исправить canonical create request и frontend key lifecycle.
- [ ] Сериализовать dispatch, сделать его повторяемым и добавить unique event.
- [ ] Добавить durable station claim/lease/fencing и проверку active jobs на
  draft, preflight и dispatch.
- [ ] Защитить outbox completion owner/token проверкой.

**Gate:** конкурентные create/dispatch и duplicate delivery создают один job,
один event и одного владельца каждой станции в PostgreSQL tests.

### 41.3. Checkpointed publish и безопасные TrueNAS retries

- [ ] Добавить additive migration для execution plan/checkpoints и job
  `recovery_required`.
- [ ] Сохранять old/desired mapping до writes и commit-ить каждую стадию.
- [ ] Разделить read retry и write unknown-outcome reconciliation.
- [ ] Сделать executor resumable; классифицировать retryable/permanent/unknown
  errors; настроить bounded Dramatiq retry.
- [ ] Перевести terminal relay/worker failures в видимое состояние job.

**Gate:** fault injection до/после каждого TrueNAS side effect и каждого DB
commit не создаёт второй объект, не теряет old mapping и либо завершает resume,
либо останавливается в `recovery_required`.

### 41.4. Safety gate перед switch и реальный verify агента

- [ ] Повторить preflight в dispatch и непосредственно перед station switch.
- [ ] Реализовать отдельное hot-switch confirmation и ограничить его область.
- [ ] Запросить post-switch refresh и привязать verify к более новому snapshot.
- [ ] Исправить job/target read model и recovery UI.

**Gate:** процесс, запущенный после prepare, stale heartbeat и пропавший `D:`
останавливают switch/verify; старый snapshot не даёт `VERIFIED`.

### 41.5. Idempotent cleanup

- [ ] Ввести cleanup request/outbox, claim и per-artifact checkpoint.
- [ ] Перепроверять live mapping непосредственно перед delete.
- [ ] Reconcile потерянный delete response чтением dataset inventory.
- [ ] Защитить periodic scheduler от Redis/send failure.

**Gate:** повтор/конкуренция/потерянный ответ не удаляют current dataset, а
отсутствующий после unknown dataset фиксируется как один успешный результат.

### 41.6. Recoverable enrollment и heartbeat

- [ ] Добавить versioned agent-owned credential enrollment с request ID.
- [ ] Сохранить переходную совместимость native/legacy agent.
- [ ] Добавить `snapshot_id` и DB dedupe heartbeat.
- [ ] Исправить классификацию HTTP ошибок и изоляцию invalid command.

**Gate:** потеря enrollment/heartbeat response восстанавливается повтором;
невалидная command не останавливает службу агента.

### 41.7. Миграция и acceptance

- [ ] Запустить полный Python suite, Ruff check/format, frontend tests/build и
  native `.NET` tests/build.
- [ ] Добавить PostgreSQL integration profile: row locks, unique races,
  `SKIP LOCKED`, lease expiry/fencing и concurrent dispatch.
- [ ] Выполнить migration upgrade/downgrade/upgrade на изолированных SQLite и
  PostgreSQL; downgrade не удаляет созданные TrueNAS объекты.
- [ ] На переходный период читать старый и новый payload Dramatiq; перед
  удалением fallback контролируемо дренировать старые Redis messages.
- [ ] Обновить `STATE.md`, operator docs и recovery runbook.

**Gate:** локальные и PostgreSQL проверки проходят; live apply остаётся
выключен до отдельного one-station smoke.

## Ключевые тестовые сценарии

- две станции с одинаковым `display_name` и rename между доставками;
- duplicate target name/ID, extent ID и association/LUN;
- два job на одну станцию, два dispatch одного job и два relay владельца;
- потеря ответа после snapshot create, clone create, extent update и delete;
- падение до write, после write/read-back и до/после DB commit каждой стадии;
- redelivery после истечения lease и stale worker completion;
- игра запускается после prepare; heartbeat устаревает перед switch;
- mapping верен, но post-switch heartbeat отсутствует или `D:` недоступен;
- повтор HTTP create после потерянного ответа и одновременный insert одного key;
- cleanup выбран до publish, но к моменту delete artifact стал current;
- enrollment commit успешен, HTTP response потерян; heartbeat response потерян;
- invalid/bad-signature command и постоянные 401/403/422;
- recovery UI для `TargetStatus.RECOVERY_REQUIRED`.

## Rollout и совместимость

1. Оставить `TRUENAS_APPLY_ENABLED=false` и cleanup apply выключенным.
2. Выполнить expand migration: только additive nullable fields/tables/indexes,
   затем read-only audit mapping/active jobs. Дубликаты исправляются оператором,
   не миграцией.
3. Job, уже находящиеся в `publishing/switching/verifying` без новых
   checkpoints, не возобновлять автоматически: сверить live mapping и перевести
   в `recovery_required` с evidence.
4. Развернуть server с backward-compatible agent protocol, затем обновить
   native agent и проверить dedupe/re-enrollment без ротации рабочих secrets.
5. Проверить fake/dry-run и PostgreSQL concurrency profile.
6. Отдельно согласовать one-station live apply: snapshot/clone/switch/agent
   verify без cleanup. Проверить повтор того же job после искусственно
   потерянного локального ответа только на заранее подготовленном test target.
7. После успешного one-station gate проверить несколько станций. Cleanup apply
   включать последним отдельным gate.
8. Contract migration с удалением legacy fallback выполнять только после
   обновления agents, дренирования старых сообщений и подтверждённого rollout.

## Запреты

- Не выполнять blind retry TrueNAS write.
- Не вычислять old mapping заново после начала внешних операций.
- Не удерживать SQL-транзакцию во время сетевого TrueNAS/agent вызова.
- Не освобождать station claim при unknown outcome до reconciliation.
- Не удалять и не переименовывать legacy datasets/snapshots автоматически.
- Не скрывать collision, stale, recovery или permanent error общим `failed`.
- Не помещать TrueNAS key, agent credential или enrollment token в DB event,
  audit, UI, exception text либо test fixtures.

## Статус

План составлен по независимому ревью. Реализация не начата.
