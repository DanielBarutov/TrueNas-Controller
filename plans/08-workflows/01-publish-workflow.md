# 08. Рабочие процессы публикации

## Цель

Реализовать публикацию как последовательность проверяемых и возобновляемых стадий, где каждая станция имеет независимый результат.

Долгие стадии выполняются worker **Dramatiq** через Redis; HTTP API только создаёт команды и возвращает состояние job.

## Preflight policy

Для admin и client собрать:

- agent online/fresh heartbeat;
- fresh process snapshot;
- required closed rules;
- `D:` present и free space threshold;
- role/tag-specific rules;
- target/initiator mapping;
- отсутствие участия в другом активном job;
- отсутствие unknown/recovery state;
- соответствие expected version/marker, если задано.

Результат каждой проверки: `pass`, `block`, `unknown`, `warning`, code, human message, observed_at, source snapshot ID. `unknown` не превращается в pass.

## Stage 0: draft

Создать job с label, description, game, mode, `dry_run=true`, `allow_hot_switch=false`. Сохранить operator и idempotency key. Выбранные station IDs материализуются в `publish_targets`, чтобы последующие изменения реестра не меняли историю job.

## Stage 1: admin

Запросить refresh admin agent. Получить snapshot, применить rules role=admin. Показывать имя и PID каждого blocking процесса. При block wizard остаётся на шаге и не позволяет перейти дальше.

## Stage 2: human confirmation

Показать «Все игровые клиенты/игры на выбранных ПК закрыты?». При `Нет` job остаётся blocked/awaiting confirmation. При `Да` записать actor, timestamp и exact confirmation result в audit. Human confirmation не заменяет agent preflight.

## Stage 3: client selection/preflight

Показать все enabled/disabled/offline/stale станции, но selectable только те, у кого нет blocking preflight, свежи snapshot и mapping. Оператор может снять отдельную станцию. Backend снова вычисляет результат при каждой apply-команде.

## Stage 4: master publish

Под lock:

1. Рассчитать canonical master label из job ID/validated label.
2. Read-check master source.
3. В dry-run только построить intended actions.
4. В apply создать один snapshot master.
5. Read-back snapshot и сохранить opaque ref.
6. Для каждой выбранной станции создать ровно один writable clone.
7. Read-back clone metadata/ownership.

Сбой clone одной станции не уничтожает master и не меняет старые mappings других станций.

## Stage 5: switch

Перед каждым target:

1. Reload station/job/target.
2. Проверить lock и отсутствие concurrent job.
3. Получить fresh agent snapshot.
4. При `idle_only` убедиться, что required processes закрыты.
5. Проверить old mapping и new mapping ownership.
6. В dry-run записать intended switch без изменения NAS.
7. В apply выполнить switch через adapter.
8. При timeout перейти в unknown и выполнить read-back.
9. Записать old/new mapping и progress.

Hot switch требует explicit flag, permission, warning и audit; по умолчанию запрещён.

## Stage 6: verify

Проверить независимо по станции:

- agent снова отвечает;
- `D:` present;
- expected marker/label;
- тестовый путь игры доступен;
- target→extent mapping соответствует новой версии;
- old mapping retained in history.

При mismatch target остаётся `error`/`recovery_required`, old mapping сохраняется, успешные targets не откатываются автоматически.

## Stage 7: finish

- Все targets verified → `completed`.
- Есть verified и error → `partial_failure`.
- Нет verified или master failure → `failed`.
- Audit и report immutable enough for operator review.
- Cleanup не запускается автоматически.

## Rollback

Rollback одной станции:

1. Найти last known good old mapping/version.
2. Получить read-back current mapping.
3. Проверить, что old object retained и принадлежит station.
4. В dry-run показать intended rollback.
5. В apply вернуть old mapping.
6. Read-back, запросить fresh agent snapshot и записать result.

Если old mapping отсутствует или ownership не подтверждён, остановиться и потребовать ручного восстановления; не выбирать объект по имени «похожий на старый».

## Cleanup

Отдельный use case после ручного теста: retention policy, list candidates, dry-run report, explicit confirmation, backup/audit gate. Любой destroy — будущий отдельный этап с собственным планом и тестами.
