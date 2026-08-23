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
- **Активный план:** [18 — wizard gating](/home/daniel/tnas/plans/18-wizard-gating/01-confirmation-selection-gate.md).
- **Текущая задача:** завершить read-only/preflight safety boundary и подготовить draft publish job/fake worker.
- **Следующий разрешённый шаг:** добавить Dramatiq/Redis fake publish workflow; реальный NAS и storage write остаются запрещёнными.
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
| [06 — Windows-агент](plans/06-agent/01-windows-agent.md) | `open` | план написан; runtime-кода нет | mock `psutil` и enrollment |
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
| [18 — Wizard gating](plans/18-wizard-gating/01-confirmation-selection-gate.md) | `in_progress` | admin/client gate, confirmation и selection invariants покрыты 4 domain-тестами | Dramatiq fake publish workflow |

## Чекап решений

- [x] Worker: **Dramatiq**.
- [x] Broker для Dramatiq: Redis, согласно исходной архитектуре.
- [x] Авторизация приложения: **HTTP Basic Auth**.
- [x] Логин приложения: `admin`.
- [x] Пароль приложения не хранится в репозитории; runtime-конфигурация — `BASIC_AUTH_PASSWORD`.
- [x] TrueNAS API key остаётся отдельным backend/worker secret и не связан с Basic Auth приложения.
- [x] Официальная документация TrueNAS найдена и занесена в [docs/ONLINE_DOCS.md](docs/ONLINE_DOCS.md).
- [ ] Проверить фактическую версию и `/api/docs/` конкретного NAS в LAN.
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
