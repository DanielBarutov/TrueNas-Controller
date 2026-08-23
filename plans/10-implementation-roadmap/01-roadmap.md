# 10. Дорожная карта реализации

## Порядок и контрольные точки

### Этап 1. Проектирование — завершён

Артефакты:

- планы 00–10;
- `PROJECT_RULES.md`, план 11 и корневой `pyproject.toml`;
- будущий `docs/ONLINE_DOCS.md` с официальными источниками;
- схема БД и state machine;
- threat model;
- mock API contract.

Запрет: не писать storage write operations.

Результат: контекст, архитектура, правила разработки, официальные TrueNAS
источники и mock safety boundary зафиксированы в планах 00–11.

### Этап 2. Каркас и read-only backend

**Текущий этап.** Bootstrap-каркас, SQLAlchemy models/UoW, read-only API,
station lifecycle, preflight core/API и wizard gate выполнены по планам 12–18.
Следующий подшаг — draft publish job и deterministic fake workflow через
Dramatiq/Redis boundary без реального TrueNAS.

Создать Python package layout по `PROJECT_RULES.md`, repository structure, Compose, `.env.example`, health, stations CRUD/soft delete, process rules, enrollment records, heartbeat intake, dashboard read-model. TrueNAS отсутствует или read-only mock.

Сначала определить Protocol ports, application use cases и UoW boundary, затем подключать FastAPI presentation и SQLAlchemy repository. `main.py` только собирает зависимости и запускает приложение.

Перед этапом показать: изменяемые модели, API routes, migration plan, tests.

Выход: API запускается, БД мигрирует, station/agent lifecycle тестируется.

### Этап 3. Windows-агент

Реализовать process/drive snapshots, enrollment, heartbeat, reconnect, refresh command и service wrapper abstraction. Сначала mock endpoint и unit tests, затем пакетирование.

Выход: агент не содержит TrueNAS secret, сервер корректно показывает online/stale/offline.

### Этап 4. Preflight wizard

Добавить admin/client checks, editable rules, human confirmation, checkbox multi-select, per-station result, server-side gating и event/read-model. Только read-only storage.

Выход: нельзя перейти к publish/switch при blocking или stale.

### Этап 5. Mock publish workflow

Подключить **Dramatiq** и fake adapter: master snapshot, clone, simulated switch, verify, progress, partial failure, idempotency, recovery unknown state и rollback. `dry_run=true` default.

Выход: acceptance сценарий проходит без TrueNAS сети.

### Этап 6. Документированный TrueNAS adapter

Открыть online docs, сверить versioned JSON-RPC methods, заполнить fixtures/registry, добавить read-only adapter. Реальный NAS ещё не используется без согласования.

Выход: method contracts имеют источники и тесты.

### Этап 7. Реальный read-only integration

На согласованном LAN подключить backend/worker secret, выполнить health/read-only discovery, сверить target/extent/zvol mapping. Никакого switch/destroy.

Выход: documented version и фактическая `/api/docs/` не расходятся по нужным read-only операциям.

### Этап 8. Безопасный apply на одной станции

Включить snapshot/clone/switch capability через explicit environment. Только одна выделенная тестовая станция, dry-run сначала, затем apply. Hot switch выключен, idle-only policy.

Выход: новая версия проходит verify, old mapping сохранён, audit полный.

### Этап 9. Массовый выбор и частичный успех

Расширить apply на несколько выбранных станций, проверить concurrency lock, partial failure, retry, independent verify и report.

Выход: критерий MVP из `CODEX.md` выполнен.

### Этап 10. Rollback и cleanup

Rollback одной станции — после успешного single-station apply. Cleanup — после manual test, retention, backup и отдельного approval; destroy не добавлять автоматически.

Выход: проверены recovery runbooks и безопасная эксплуатация.

## Gate между этапами

Перед переходом проверить:

- план этапа обновлён;
- модели и миграции перечислены;
- тесты перечислены и имеют expected outcomes;
- запреты текущего этапа соблюдены;
- нет невосстановленного unknown state;
- аудит и логи не содержат секреты;
- следующая опасность явно согласована.

## Порядок первой реализации

1. Прочитать планы и подтвердить выбранные спорные решения.
2. Создать минимальный каркас и конфигурацию.
3. Добавить БД/миграции и health.
4. Реализовать station/agent read-only lifecycle.
5. Добавить тесты до перехода к worker.
6. Только затем реализовать preflight и mock workflow.

## Критерий MVP

Оператор добавляет произвольное количество ПК, выбирает несколько online/idle станций, проходит preflight, создаёт одну master-версию, переключает выбранные targets, видит независимый verify каждого ПК и может откатить одну станцию. Никаких необратимых операций без dry-run и явного подтверждения.

## Что считать остановкой

Работу останавливать и фиксировать blocker, если:

- официальная документация не подтверждает нужный TrueNAS method;
- фактический mapping расходится с ожидаемым;
- worker не может определить результат write operation;
- нет свежего agent snapshot;
- не удаётся доказать, что старый mapping сохранён;
- попытка требует обхода TLS/auth/anti-safety policy.
