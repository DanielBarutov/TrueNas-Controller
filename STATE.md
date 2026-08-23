# STATE — состояние проекта

Последнее обновление: **2026-08-23**

## Как читать этот файл

Этот файл открывается перед каждой рабочей сессией. Он показывает, какой план активен, какие планы закрыты на текущей стадии проектирования, какие ещё открыты и какие проверки не пройдены.

Статус относится к текущей стадии проекта, а не означает, что код соответствующего слоя уже реализован:

- `in_progress` — текущая рабочая область;
- `closed` — планирование области зафиксировано на текущей стадии;
- `open` — план есть, но реализация/следующая проверка ещё не начата;
- `blocked` — работа остановлена по конкретной причине.

## Текущая стадия

- **Стадия:** 2 — каркас и read-only backend.
- **Активный план:** [30 — TrueNAS LAN integration gate](/home/daniel/tnas/plans/30-truenas-lan-gate/01-local-api-docs-and-connection.md).
- **Текущая задача:** завершить docs gate; версия `25.10.5` и live `/api/docs/current/` сверены, opt-in runtime boundary создан, read-only smoke check ещё не выполнялся. Параллельно подготовлен безопасный local collector slice Windows-агента.
- **Следующий разрешённый шаг:** после отдельного явного согласования и внешней runtime-конфигурации API key выполнить только `core.ping`/query; real Redis execution и storage write пока не включать.
- **Запрещено сейчас:** подключение к реальному NAS, реальные mapping switch и любые `destroy/delete` storage-объектов.

## Статус планов

| План | Статус | Чекап текущей стадии | Следующая проверка |
|---|---|---|---|
| [00 — Контекст](plans/00-context.md) | `closed` | `CODEX.md` изучен; границы MVP записаны | обновлять только при изменении требований |
| [01 — Архитектура](plans/01-architecture/01-layers.md) | `closed` | слои, зависимости и package layout сверены с каркасом | сверять при добавлении новых adapters |
| [02 — БД](plans/02-database/01-schema.md) | `closed` | сущности, связи и инварианты описаны | проверить перед первой миграцией |
| [03 — State machine](plans/03-state-machine/01-state-machine.md) | `closed` | состояния и переходы описаны | покрыть переходы unit-тестами |
| [04 — Безопасность](plans/04-security/01-security.md) | `closed` | секреты, audit и Basic Auth зафиксированы | проверить реализацию auth и redaction |
| [05 — API](plans/05-api/01-contract.md) | `closed` | endpoint-контракты описаны | проверить схемы через contract tests |
| [06 — Windows-агент](plans/06-agent/01-windows-agent.md) | `open` | config, collectors, heartbeat/retry, enrollment coordinator и service boundary созданы; Windows ACL/DPAPI, command delivery и native wrapper ещё нет | native credential/service integration и marker decision |
| [07 — TrueNAS adapter](plans/07-truenas-adapter/01-adapter.md) | `open` | официальные docs и методы собраны; NAS не подключён | зафиксировать fixtures и mock contract |
| [08 — Workflows](plans/08-workflows/01-publish-workflow.md) | `open` | workflow описан; apply не реализован | acceptance на fake adapter |
| [09 — Тестирование](plans/09-testing/01-strategy.md) | `open` | стратегия описана; тестового каркаса нет | выбрать команды и написать первые unit-тесты |
| [10 — Roadmap](plans/10-implementation-roadmap/01-roadmap.md) | `closed` | этапы и gates зафиксированы | обновлять при принятии новых решений |
| [11 — Правила разработки](plans/11-project-rules/01-development-rules.md) | `closed` | чистая архитектура, UoW, Protocol, тесты и Ruff зафиксированы | применять при создании package layout |
| [12 — Bootstrap backend](plans/12-read-only-backend/01-bootstrap.md) | `closed` | package layout, domain Station, Protocol ports и 5 domain-тестов созданы | persistence проверен планом 13 |
| [13 — Persistence](plans/13-persistence/01-models-uow.md) | `closed` | две ORM-модели, station repository, concrete UoW и 5 persistence-тестов созданы | применяется в API плане 14 |
| [14 — Read-only API](plans/14-read-only-api/01-health-stations-auth.md) | `closed` | health, stations list, Basic Auth, Alembic config и API/application-тесты созданы | применяется lifecycle планом 15 |
| [15 — Agent lifecycle](plans/15-agent-lifecycle/01-registry-enrollment-heartbeat.md) | `closed` | registry, one-shot enrollment, hashed credentials, heartbeat и lifecycle tests созданы | preflight core план 16 |
| [16 — Preflight core](plans/16-preflight-core/01-process-rules-evaluator.md) | `closed` | evaluator, process/drive/freshness checks и 7 domain-тестов созданы | применяется планом 17 |
| [17 — Preflight API](plans/17-preflight-api/01-rules-snapshot-query.md) | `closed` | process rules, latest snapshot query, application preflight и API smoke созданы | применяется wizard планом 18 |
| [18 — Wizard gating](plans/18-wizard-gating/01-confirmation-selection-gate.md) | `closed` | admin/client gate, confirmation и selection invariants покрыты 4 domain-тестами | применяется mock publish планом 19 |
| [19 — Mock publish](plans/19-mock-publish/01-dramatiq-fake-workflow.md) | `closed` | uv dependencies, job state machine, fake adapter/workflow и actor boundary покрыты 10 тестами | publish persistence |
| [20 — Publish persistence](plans/20-publish-persistence/01-job-target-uow.md) | `closed` | `publish_jobs`/`publish_targets`, stable station mapping, constraints, rollback и worker reload покрыты 8 тестами | draft command/enqueue |
| [21 — Draft command](plans/21-draft-command/01-create-and-enqueue.md) | `closed` | draft use case, idempotency conflict, fresh state read и minimal queue adapter покрыты 5 тестами | presentation draft route |
| [22 — Publish presentation](plans/22-publish-presentation/01-create-draft-route.md) | `closed` | POST draft route, Basic Auth, 422/409 mapping и safe response покрыты 2 API-тестами | job read model |
| [23 — Publish read model](plans/23-publish-read-model/01-job-status-query.md) | `closed` | application query, Basic Auth GET, 404 и safe target status покрыты 4 тестами | operator confirmation |
| [24 — Publish confirmation](plans/24-publish-confirmation/01-confirmation-command.md) | `closed` | persisted preflight, wizard gate, confirmation timestamp и blocked state покрыты 5 тестами | safe dispatch |
| [25 — Publish dispatch](plans/25-publish-dispatch/01-safe-enqueue-gate.md) | `closed` | status transition, confirmation/preflight gate и queue-after-UoW покрыты 4 тестами | transactional outbox |
| [26 — Publish outbox](plans/26-publish-outbox/01-transactional-outbox-retry.md) | `closed` | atomic dispatch event, lease/recovery, relay delivery, retry и terminal failure покрыты 6 тестами | fake worker executor |
| [27 — Fake worker executor](plans/27-fake-worker-executor/01-persisted-workflow-results.md) | `closed` | fake task executor и persisted simulated/verified/partial outcomes покрыты 4 тестами | fake acceptance |
| [28 — Fake acceptance](plans/28-fake-acceptance/01-end-to-end-pipeline.md) | `closed` | полный SQLite pipeline create→preflight→outbox→relay→fake worker→verified и duplicate delivery покрыты 1 acceptance-тестом | read-only TrueNAS adapter |
| [29 — TrueNAS read-only adapter](plans/29-truenas-read-only/01-versioned-adapter-contract.md) | `closed` | transport, registry, fixture mapper и contract tests; `93 passed` | применять через LAN gate 30 |
| [30 — TrueNAS LAN integration gate](plans/30-truenas-lan-gate/01-local-api-docs-and-connection.md) | `in_progress` | версия/live docs подтверждены; runtime config/auth boundary создан; JSON-RPC smoke check не выполнялся | отдельное согласование read-only smoke check |

## Чекап решений

- [x] Worker: **Dramatiq**.
- [x] Broker для Dramatiq: Redis, согласно исходной архитектуре.
- [x] Авторизация приложения: **HTTP Basic Auth**.
- [x] Логин приложения: `admin`.
- [x] Пароль приложения не хранится в репозитории; runtime-конфигурация — `BASIC_AUTH_PASSWORD`.
- [x] TrueNAS API key остаётся отдельным backend/worker secret и не связан с Basic Auth приложения.
- [x] Официальная документация TrueNAS найдена и занесена в [docs/ONLINE_DOCS.md](docs/ONLINE_DOCS.md).
- [x] Проверить фактическую версию `25.10.5` и live `/api/docs/current/` конкретного NAS через временный доступ; runtime smoke check отдельно.
- [ ] Согласовать формат `game_version_marker` и тестовый путь игры.
- [x] Чистая архитектура: `presentation`, `application`, `repository`, `domain`.
- [x] Порты через `Protocol`, без `abc.ABC`.
- [x] UoW с новым экземпляром на каждый use case/Dramatiq task.
- [x] Ruff config добавлен в `pyproject.toml`.
- [x] Package layout создан согласно архитектурным правилам.
- [x] Domain не импортирует инфраструктуру.
- [x] Первый ключевой набор domain-тестов: `5 passed`.
- [x] Корневой `.gitignore` добавлен для Python, тестовых/линтер-кэшей, IDE и локальных секретов.
- [x] SQLAlchemy models для `stations`/`agents` созданы без применения миграций.
- [x] Concrete UoW создаёт новую session на каждый вызов; commit/rollback проверены.
- [x] Repository/UoW тесты: `10 passed` всего.
- [x] Реальный PostgreSQL и NAS не подключались.
- [x] Read-only API создаётся через composition root; Basic Auth fail-closed проверен.
- [x] Alembic config подключён, revision не создавалась и миграции не применялись.
- [x] Общий набор тестов: `14 passed`.
- [x] Agent lifecycle: one-shot enrollment, credential hash, binding и heartbeat проверены.
- [x] Process preflight: block/warning/unknown, drive threshold и station binding проверены.
- [x] Общий набор тестов после lifecycle/preflight: `25 passed`.
- [x] Process rules persistence и latest snapshot query проверены на SQLite.
- [x] `POST /api/v1/preflight` требует operator Basic Auth и возвращает explainable checks.
- [x] Общий набор тестов после rules/preflight API: `29 passed`.
- [x] Wizard gate проверяет admin/client reports, confirmation и server-side selection.
- [x] Общий набор тестов после wizard gate: `33 passed`.
- [x] Dramatiq/Redis project dependencies зафиксированы в `pyproject.toml` и `uv.lock`.
- [x] Fake publish проверяет dry-run, idempotent master/clone, partial failure и unknown read-back.
- [x] Dramatiq actor получает только IDs/idempotency/correlation и создаёт fresh handler per message.
- [x] Общий набор тестов после fake publish: `43 passed` на Python 3.12/uv.
- [x] `publish_jobs`/`publish_targets` repositories проверяют stable station IDs, unique constraints и atomic rollback.
- [x] Dramatiq composition handler перечитывает job/targets в свежем UoW и отклоняет mismatched payload.
- [x] Общий набор тестов после publish persistence: `51 passed` на Python 3.12/uv.
- [x] Draft application use case повторно проверяет station selection, idempotency и safe defaults.
- [x] Queue port/adapter передаёт только job/correlation/idempotency primitives; Redis broker не запускался.
- [x] Общий набор тестов после draft/enqueue: `56 passed` на Python 3.12/uv.
- [x] POST draft route подключён через Basic Auth и не enqueue-ит worker автоматически.
- [x] Общий набор тестов после presentation draft route: `58 passed` на Python 3.12/uv.
- [x] GET job read model возвращает per-target statuses/progress без raw mappings и требует Basic Auth.
- [x] Общий набор тестов после publish read model: `62 passed` на Python 3.12/uv.
- [x] Persisted preflight повторно вызывает wizard gate, сохраняет target reports и confirmation timestamp без enqueue.
- [x] Общий набор тестов после confirmation/preflight: `68 passed` на Python 3.12/uv.
- [x] Dispatch gate переводит только safe job в `publishing`, закрывает UoW до queue call и не запускает broker.
- [x] Общий набор тестов после dispatch gate: `72 passed` на Python 3.12/uv.
- [x] Transactional outbox атомарно фиксирует dispatch event; relay использует lease, retry/backoff и secret-free payload.
- [x] Общий набор тестов после outbox/relay: `78 passed` на Python 3.12/uv.
- [x] Fake worker executor сохраняет dry-run/apply/partial outcomes и не создаёт новые fake objects для terminal duplicate delivery.
- [x] Общий набор тестов после fake executor: `82 passed` на Python 3.12/uv.
- [x] End-to-end fake acceptance прошёл create→preflight→dispatch→relay→worker→verified и duplicate delivery.
- [x] Общий набор тестов после fake acceptance: `83 passed` на Python 3.12/uv.
- [x] Versioned TrueNAS read-only adapter: DTO, Protocol, JSON-RPC transport, registry, fixture и mapper contract tests.
- [x] Ruff check/format после adapter slice: passed.
- [x] Общий набор тестов после read-only adapter: `93 passed` на Python 3.12/uv.
- [x] Live docs gate: `/api/docs/current/` подтвердил `TrueNAS API v25.10.5 (current)` и read-only method allow-list; без API key и JSON-RPC calls.
- [x] Opt-in TrueNAS runtime boundary: `TRUENAS_WS_URL`/`TRUENAS_API_KEY` не имеют defaults, auth redacted, smoke test skipped by default.
- [x] Windows-agent local collectors: process/drive/snapshot core и ключевые tests; network/service runtime не запускались.
- [x] Windows-agent heartbeat slice: versioned payload, HTTPS transport, bounded retry и safe command validator; внешний network не запускался.
- [x] Windows-agent lifecycle slice: fail-closed config, atomic credential fallback, one-shot enrollment coordinator, command handler и graceful service boundary; native Windows integration не запускалась.
- [x] Server-agent heartbeat contract: protocol `1`, hostname/IP/MAC validation and persistence; migrations не менялись.
- [x] Общий набор тестов после agent/server contract slice: `125 passed, 1 skipped` на Python 3.12/uv.
- [x] Redis broker execution и настоящий TrueNAS не запускались.

## Решение, которое требует объяснения

Вопрос про `game_version_marker` означает: **как агент поймёт после переключения, что новая версия игры действительно доступна?**

Примеры: marker-файл на `D:`, label/metadata zvol или заранее известный тестовый путь вроде `D:\Games\<game>`. Это не нужно решать прямо сейчас; до выбора оставляем verify в состоянии `pending decision`.

## История изменений состояния

| Дата | Изменение | Причина |
|---|---|---|
| 2026-08-23 | Создан `STATE.md`, назначен активный план 07 | Нужен единый контроль контекста |
| 2026-08-23 | Выбран Dramatiq | Решение пользователя |
| 2026-08-23 | Выбран HTTP Basic Auth с пользователем `admin` | Решение пользователя; пароль не фиксируется в repo |
| 2026-08-23 | Добавлен список официальных TrueNAS docs и API methods | Подготовка adapter без подключения к NAS |
| 2026-08-23 | Добавлены `PROJECT_RULES.md`, план 11 и Ruff baseline | Зафиксированы правила архитектуры и разработки |
| 2026-08-23 | Добавлен план 12 и bootstrap package layout | Начат этап read-only backend; создана граница domain/application |
| 2026-08-23 | Добавлен корневой `.gitignore` | Исключены кеши Python, утилит, IDE, локальные данные и секреты |
| 2026-08-23 | Добавлен план 13 и persistence slice | Созданы ORM models, station repository и concrete UoW; миграции не применялись |
| 2026-08-23 | Добавлен план 14 и минимальный read-only API | Health, stations list, Basic Auth и Alembic config; TrueNAS не подключался |
| 2026-08-23 | Добавлены планы 15–16 | Реализованы agent lifecycle и чистый preflight evaluator; TrueNAS write не добавлялся |
| 2026-08-23 | Добавлен план 17 | Process rules persistence, latest snapshot query и preflight API; publish не запускался |
| 2026-08-23 | Добавлен план 18 | Реализован preflight wizard safety gate; worker/NAS не запускались |
| 2026-08-23 | Добавлен план 19 | Добавлены Dramatiq dependencies, publish state machine, fake workflow и actor boundary |
| 2026-08-23 | Добавлены планы 20–21 | Job/target persistence и worker composition завершены; начат application draft command и queue port |
| 2026-08-23 | Добавлен план 22 | Draft/enqueue boundary завершены; начат Basic Auth presentation route для создания draft |
| 2026-08-23 | Добавлен план 23 | POST draft route завершён; начат безопасный GET job read model |
| 2026-08-23 | Добавлен план 24 | GET read model завершён; начат persisted operator confirmation/preflight gate |
| 2026-08-23 | Добавлен план 25 | Confirmation/preflight gate завершён; начат safe dispatch gate перед enqueue |
| 2026-08-23 | Добавлен план 26 | Dispatch gate завершён; commit/queue gap вынесен в transactional outbox plan |
| 2026-08-23 | Добавлен план 27 | Outbox/relay завершены; начат fake worker executor с persisted results |
| 2026-08-23 | Добавлен план 28 | Fake executor завершён; начат end-to-end acceptance полного pipeline |
| 2026-08-23 | Добавлен план 29 | End-to-end fake pipeline завершён; начат versioned TrueNAS read-only adapter contract |
| 2026-08-23 | Завершён план 29 и добавлен план 30 | Read-only adapter contract/fixtures прошли `93 passed`; LAN integration оставлен отдельным opt-in gate |
| 2026-08-23 | Обновлён план 30 | Live docs endpoint подтвердил TrueNAS API v25.10.5 и read-only methods; smoke check/API key остаются отдельным согласованием |
| 2026-08-23 | Продолжен план 30 | Добавлены opt-in WebSocket factory, API-key auth boundary и smoke test без запуска по умолчанию |
| 2026-08-23 | Подготовлен безопасный agent slice | Добавлены local process/drive/snapshot collectors; внешний NAS, heartbeat network и Windows Service не запускались |
| 2026-08-23 | Продолжен план 06 | Добавлены versioned heartbeat payload, HTTPS transport, bounded retry и safe refresh command validator; внешний network не запускался |
| 2026-08-23 | Продолжен план 06 | Добавлены fail-closed config, credential store boundary, one-shot enrollment coordinator и graceful service lifecycle; native Windows integration не запускалась |
| 2026-08-23 | Замкнут heartbeat metadata contract | protocol `1`, hostname/IP/MAC validation и persistence добавлены без миграций; внешний agent/network не запускался |
