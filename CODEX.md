# Промпт проекта: Game Update Controller для TrueNAS iSCSI

Скопируй текст ниже в Codex/ИИ-разработчику. Это техническое задание на локальное приложение, которое уменьшает ручную работу при обновлении игровых дисков. Не привязывай проект к восьми ПК: оператор сам регистрирует, отключает и удаляет станции.

## 1. Цель и границы

Нужно создать безопасный контроллер публикации обновлений игр для игрового клуба. TrueNAS SCALE хранит эталонную библиотеку на ZFS и отдельные клоны/тома для клиентов, подключённые по iSCSI. Windows на каждом клиенте установлена на локальном `C:`, а игры находятся на iSCSI-диске `D:`.

Оператор должен в веб-интерфейсе:

- сам добавлять любое количество игровых ПК и админский ПК;
- видеть online/offline, heartbeat, IP/MAC, версию агента, доступность `D:` и процессы;
- выбрать несколько ПК флажками;
- пройти пошаговую проверку перед обновлением;
- один раз создать новую версию master-диска и переключить только выбранные станции;
- получать прогресс, красные флаги, частичные ошибки и результат проверки каждого ПК;
- выполнить rollback по одной станции без уничтожения старой рабочей версии.

Веб-интерфейс достаточен для управления оператором, но сам по себе не может достоверно узнать процессы Windows и состояние `D:`. Поэтому нужен лёгкий Windows-агент на каждом зарегистрированном клиенте и на админском ПК. Агент не получает ключ TrueNAS и не управляет iSCSI напрямую: он только сообщает состояние контроллеру.

## 2. Предлагаемая архитектура

Приложение запускается через Docker Compose на любом постоянно включённом ПК/мини-сервере в той же LAN, где доступны TrueNAS и игровые станции. Это не обязано быть TrueNAS-приложение. Если хост уснёт или выключится, веб-контроллер и фоновые задания недоступны; это должно явно отображаться в UI.

```text
Windows-агенты (клиенты + admin)
          │ outbound HTTPS/WebSocket, heartbeat и process snapshot
          ▼
  Caddy/Nginx (опционально TLS) ── React/Vite web UI
          │
          ▼
  FastAPI API ── PostgreSQL ── Redis ── durable worker
          │
          ▼
  TrueNAS adapter: versioned JSON-RPC 2.0 over WebSocket
```

Рекомендуемый стек MVP:

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy/Alembic;
- PostgreSQL для станций, агентов, правил процессов, заданий, версий и аудита;
- Redis + отдельный worker (RQ/Celery/Arq) для длительных publish/switch/verify задач;
- React + Vite + TypeScript для UI;
- Python-агент с `psutil`, работающий как Windows Service (NSSM/WinSW или нативный service wrapper);
- `pytest` для API, workflow, адаптера и mock-агента;
- REST допустим для собственного API приложения. Для TrueNAS использовать только его JSON-RPC WebSocket API.

Для однопользовательского пробного запуска допускается SQLite вместо PostgreSQL, но границы repository должны позволять перейти к PostgreSQL без переписывания workflow.

## 3. Онлайн-документация TrueNAS до подключения к сети

Во время разработки контроллер не должен требовать доступ к реальному NAS. Перед реализацией открыть официальные публичные документы онлайн и зафиксировать версию в `docs/ONLINE_DOCS.md`:

- API: <https://www.truenas.com/docs/scale/25.10/api/>;
- iSCSI shares/targets/extents: <https://www.truenas.com/docs/scale/25.10/scaletutorials/shares/iscsi/addingiscsishares/>;
- datasets, zvols, snapshots и clones: <https://www.truenas.com/docs/scale/25.10/scaletutorials/datasets/addmanagezvols/>.

Сделать `TRUENAS_VERSION` настраиваемой переменной и адаптер методов по версии. Для разработки использовать mock-клиент и fixtures JSON-RPC ответов. Онлайн-адрес `https://<NAS_IP>/api/docs/` использовать только позже, когда контроллер будет в LAN, для сверки фактической версии и имён методов. Не придумывать REST URL по аналогии с другими NAS.

TrueNAS 25.04+ использует versioned JSON-RPC 2.0 over WebSocket; API key — секрет уровня пароля. Ключ хранится только в backend/worker secret, не в браузере, не в агентах и не в репозитории.

## 4. Динамический реестр ПК

Не хардкодить `pc01`–`pc08`. В базе должны быть сущности `station`, `agent`, `process_snapshot`, `process_rule`, `storage_version`, `publish_job`, `publish_target` и `audit_event`.

Поля станции минимум:

```text
station_id (UUID/стабильный идентификатор агента)
display_name, hostname
ip_addresses[], mac_addresses[]       # справочная информация, не первичный ключ
role = admin | client
enabled, tags
target_name, target_iqn, initiator_iqn  # iSCSI-реквизиты для server-side adapter
current_version, desired_version
agent_version, last_seen, last_process_snapshot_at
state = offline | stale | online | blocked | ready | switching | verified | error
```

В UI добавить страницы/диалоги:

1. «Станции»: добавить, изменить, отключить, удалить, повторно зарегистрировать; отображать причины offline/stale и последнюю ошибку.
2. «Регистрация агента»: сгенерировать одноразовый enrollment token, показать команду установки, после регистрации token отозвать/ротировать.
3. «Правила процессов»: имя процесса, роль (`admin`/`client`), `required_closed`, severity, enabled, применяемые теги. Правила не зашивать в код.

MAC и IP не считать стабильной идентичностью: DHCP может изменить IP, а NIC — MAC. Основной ключ — выданный при enrollment `station_id`/agent UUID; MAC/IP показывать и проверять как дополнительные признаки.

## 5. Windows-агент

Агент запускается как служба и каждые 5–15 секунд отправляет heartbeat по исходящему HTTPS/WebSocket соединению. Минимальный payload:

```json
{
  "station_id": "...",
  "hostname": "PC-01",
  "ip_addresses": ["192.168.7.21"],
  "mac_addresses": ["..."],
  "agent_version": "0.1.0",
  "timestamp": "...",
  "process_snapshot_at": "...",
  "processes": [{"name": "steam.exe", "pid": 1234, "path": "..."}],
  "drives": [{"letter": "D:", "present": true, "free_bytes": 0}]
}
```

Требования:

- использовать `psutil.process_iter()` с обработкой AccessDenied/NoSuchProcess;
- не отправлять содержимое пользовательских файлов и секреты;
- не иметь TrueNAS API key;
- поддержать server-initiated refresh процесса и мягкое уведомление оператору;
- не завершать процессы принудительно. В будущем отдельный подтверждённый override может послать graceful-close, но не входит в MVP;
- сообщать свежесть данных: UI различает `healthy` (зелёный), `blocking` (красный), `unknown/stale` (серый), `offline`;
- мониторинг можно выполнять от обычной учётной записи; права `SYSTEM` не использовать без необходимости.

Примеры правил по умолчанию, которые администратор может изменить: `steam.exe`, `steamwebhelper.exe`, `EpicGamesLauncher.exe`, `EpicWebHelper.exe`, `RiotClientServices.exe`, `RiotClientUx.exe`, `RiotClientUxRender.exe`, `UbisoftConnect.exe`. `vgc.exe`/античит не считать автоматически «закрыть»: он может быть системно необходим, поэтому классифицировать отдельно как `persistent_allowed`, если это подтверждено политикой клуба.

## 6. Пошаговый веб-мастер публикации

Сделать страницу «Новое обновление» с job ID, audit log, кнопками «Назад», «Обновить проверки», «Отменить» и явными подтверждениями. Выбор станций — таблица с checkbox, фильтрами и массовыми действиями; число станций не ограничивать восьмью.

### Шаг 0 — создание задания

Оператор задаёт label, описание/игру и желаемый режим. Создать draft job с `dry_run=true` по умолчанию.

### Шаг 1 — проверка админского ПК

Админский агент (role `admin`) обновляет snapshot. UI показывает все процессы, попавшие под `required_closed`, зелёные/красные флаги, время снимка и кнопку «Повторить проверку». Если хотя бы один blocking-процесс не закрыт, переход блокируется. Не скрывать точное имя процесса и PID.

### Шаг 2 — подтверждение оператора

Показать обязательный вопрос: «Все игровые клиенты/игры на выбранных ПК закрыты?» с вариантами **Да / Нет**. При «Нет» следующий шаг недоступен. Это не заменяет автоматическую проверку агентов; это явное подтверждение человека и запись в audit log.

### Шаг 3 — выбор и preflight клиентов

Показать динамический список зарегистрированных ПК с флажками. Выбирать разрешать только станции, которые:

- enabled, online и имеют свежий heartbeat/process snapshot;
- не имеют blocking-процессов;
- имеют доступный `D:` и достаточно свободного места;
- имеют корректно зарегистрированный target/initiator mapping;
- не участвуют в другом publish job.

Оператор может выбрать несколько ПК одновременно. Для каждого выбранного ПК показать индивидуальные проверки и возможность снять флажок без отмены всего задания. Offline/stale ПК остаются видимыми, но не selectable.

### Шаг 4 — публикация master

Закрыть лаунчеры на админском ПК согласно preflight. Создать один ZFS snapshot master zvol с уникальным label. По этому snapshot создать writable clone только для выбранных станций, сохранив старые версии. Операция должна быть идемпотентной: повтор job не создаёт дубликаты.

### Шаг 5 — переключение iSCSI

Проверить target, old extent, new extent, zvol path и принадлежность станции. Не менять имя target и букву `D:`. Переключать выбранные target в worker с прогрессом по каждой станции.

Пользователь подтвердил, что в его тесте смена extent может применяться «в горячую». Реализовать это как экспериментальный feature flag `allow_hot_switch`, выключенный по умолчанию. Политика по умолчанию — `idle_only`: разрешать switch только при свежем подтверждении агента, что игра и обязательные лаунчеры закрыты. Никогда не переключать активную игру молча; горячий режим должен быть отдельно подтверждён, полностью залогирован и иметь предупреждение о том, что гарантия зависит от версии TrueNAS/Windows/iSCSI.

### Шаг 6 — верификация

После switch запросить новый process/drive snapshot. Проверить `D:` present и соответствие target→extent на TrueNAS. Факт обновления игры подтверждает оператор вне автоматического safety gate. Статус по каждой станции: `verified` или `error`; partial success допустим. Ошибочная станция сохраняет старый рабочий target и не блокирует отчёт по успешным, если это безопасно.

### Шаг 7 — завершение и rollback

Старый clone/snapshot не удалять автоматически. После ручного теста оператор может запустить cleanup с retention policy и отдельным подтверждением. Rollback должен быть доступен отдельно для каждой станции; при любой ошибке сохранять старый mapping.

Статусы job: `draft`, `preflight`, `waiting_for_admin`, `awaiting_client_confirmation`, `publishing`, `switching`, `verifying`, `completed`, `partial_failure`, `rolled_back`, `failed`.

## 7. API собственного приложения

Минимальные endpoints:

```text
POST   /api/v1/agents/enroll
POST   /api/v1/agents/heartbeat
POST   /api/v1/agents/{id}/processes/refresh
GET    /api/v1/stations
POST   /api/v1/stations
PATCH  /api/v1/stations/{id}
DELETE /api/v1/stations/{id}          # soft delete/disable по умолчанию
GET    /api/v1/stations/{id}/processes
POST   /api/v1/preflight/admin
POST   /api/v1/publish/jobs
GET    /api/v1/publish/jobs/{id}
POST   /api/v1/publish/jobs/{id}/confirm
POST   /api/v1/publish/jobs/{id}/switch
POST   /api/v1/publish/jobs/{id}/rollback
POST   /api/v1/publish/jobs/{id}/cleanup  # dry-run по умолчанию
WS     /api/v1/publish/jobs/{id}/events
GET    /api/v1/health
```

`POST /switch` принимает массив `station_ids`, но backend ещё раз проверяет каждую станцию. Browser обращается только к собственному API; TrueNAS API вызывается исключительно backend/worker адаптером.

## 8. TrueNAS adapter и storage-модель

Сделать слой `truenas_adapter` с:

```text
websocket_jsonrpc.py   # transport, request id, auth, timeout, reconnect
method_registry.py     # version -> method names/params
mock_client.py         # deterministic fake for tests
fixtures/              # responses from documented schemas
```

Адаптер должен уметь читать zvol/dataset/snapshot/clone, iSCSI target/extent/association и выполнять только явно разрешённые операции snapshot, clone и mapping switch. Все методы/параметры сверять с онлайн-документами и фактической `/api/docs/` при интеграционном тесте.

Правила хранения:

- один клиент — один собственный zvol/clone и один iSCSI LUN;
- не подключать один writable LUN одновременно к нескольким Windows ПК;
- label и station ID должны безопасно экранироваться и иметь разрешённый формат;
- master snapshot создаётся один раз на job, clone — только для выбранных станций;
- старую версию не считать удалённой, пока новая не прошла verify;
- при partial failure не выполнять разрушительный автоматический cleanup.

## 9. Безопасность и отказоустойчивость

- TrueNAS API key хранить в Docker secret/переменной окружения backend/worker, не в frontend и не в agent.
- Использовать HTTPS; отключение TLS-проверки возможно только явным локальным флагом и должно быть заметно в UI.
- Enrollment token одноразовый, с TTL и revoke; агенту выдать отдельный ограниченный credential.
- Вести audit log: кто, когда, job, станции, старый/новый zvol, target/extent IDs, подтверждения, ошибки.
- По умолчанию dry-run для publish/switch/cleanup, плюс явное подтверждение. Никаких `destroy` без отдельного шага.
- Защитить от двух параллельных publish через DB lock/advisory lock.
- Worker должен иметь retry с idempotency key, timeout и компенсационное состояние, но не удалять объекты автоматически после ошибки.
- Красный флаг не должен исчезать из-за устаревшего heartbeat; показывать timestamp и причину.
- Приложение слушает только LAN/localhost, без публикации TrueNAS API в интернет.

## 10. Структура репозитория

```text
game-update-controller/
├── compose.yaml
├── .env.example
├── README.md
├── docs/ONLINE_DOCS.md
├── api/
│   ├── app/main.py
│   ├── routers/{stations,agents,preflight,publish,health}.py
│   ├── models/
│   ├── repositories/
│   ├── services/{agent_registry,process_preflight,publish_workflow,truenas}.py
│   └── migrations/
├── worker/tasks.py
├── frontend/                 # React/Vite/TypeScript
├── agent/
│   ├── agent.py
│   ├── process_monitor.py
│   ├── enrollment.py
│   └── windows_service.py
├── truenas_adapter/
│   ├── websocket_jsonrpc.py
│   ├── method_registry.py
│   ├── mock_client.py
│   └── fixtures/
└── tests/
```

Compose-сервисы: `frontend`, `api`, `worker`, `postgres`, `redis`, опционально `caddy`. Добавить healthchecks, volume для БД и резервное копирование конфигурации/аудита. Не запускать приложение с привилегиями, достаточными для изменения ОС TrueNAS.

## 11. Этапы реализации

Не писать сразу код удаления или смены iSCSI mapping. Перед каждым следующим этапом показать план, изменённые модели и тесты.

1. **Проектирование:** структура, схема БД, state machine, угрозы, online docs и mock API.
2. **Read-only backend:** health, станции, enrollment, heartbeat, process rules, dashboard; без операций TrueNAS.
3. **Windows-агент:** installer/service, heartbeat, process snapshot, drive check, reconnect и тестовый mock endpoint.
4. **Preflight wizard:** admin/client checks, «Да/Нет» подтверждение, multi-select и красные флаги.
5. **Mock publish workflow:** snapshot/clone/switch/verify на fake TrueNAS, durable worker, progress events.
6. **Интеграционный adapter:** только после сверки методов с `/api/docs/` реального TrueNAS в LAN; сначала read-only.
7. **Безопасный apply:** dry-run, явное подтверждение, staging и switch с одной тестовой станцией, затем массовый выбор.
8. **Rollback/cleanup:** только после успешного теста и с retention/backup.

## 12. Приёмка

Предоставить:

1. `compose.yaml`, `.env.example`, инструкции локального запуска и enrollment агента;
2. UI с динамическим добавлением/отключением станций, checkbox multi-select и пошаговым мастером;
3. автоматические process/drive preflight для admin и clients с зелёными/красными/серыми статусами;
4. mock-тесты без настоящего TrueNAS и интеграционные тесты, запускаемые только отдельным флагом в LAN;
5. пример audit log, partial failure, stale agent, rollback и повторного idempotent job;
6. `OPERATIONS.md` с действиями при расхождении БД и NAS, заполнении пула выше 80%, пропавшем агенте и неудачном switch;
7. подтверждение, что секреты отсутствуют во frontend bundle, логах, agent package и git.

Критерий готовности MVP: оператор добавляет произвольное количество ПК, выбирает несколько online/idle станций, проходит preflight, создаёт одну новую master-версию, переключает выбранные targets, видит независимый verify каждого ПК и может откатить одну станцию. Никаких необратимых операций без dry-run и явного подтверждения.

Сначала покажи архитектуру, схему БД, state machine, список проверенных онлайн API-методов и план реализации. Не подключайся к реальному NAS до отдельного согласования и не пиши операции `destroy`/mapping switch до завершения mock-тестов.

## 13. Правила разработки Python-приложения

- Работать по чистой архитектуре со слоями `presentation`, `application`, `repository`, `domain`.
- `main.py` использовать только как composition root для сборки зависимостей и запуска; HTTP/WebSocket routes держать в `presentation`.
- Соблюдать SOLID и ООП; application зависит от портов, а не от concrete adapters.
- Порты описывать через `typing.Protocol`; `abc.ABC` для портов не использовать.
- Persistence и реализацию Unit of Work держать в `repository`; на каждый HTTP use case и Dramatiq task создавать свежий UoW.
- Worker — Dramatiq с Redis broker.
- Тестировать только ключевую domain/application логику, инварианты UoW и критичные adapter contracts; не добавлять лишние тесты для очевидного glue-кода.
- Использовать Ruff для lint, format и сортировки импортов согласно корневому `pyproject.toml`.
- Перед рабочей сессией читать `STATE.md` и `PROJECT_RULES.md`; после изменений обновлять состояние и чекапы.
