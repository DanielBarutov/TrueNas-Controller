# STATE — состояние проекта

Последнее обновление: **2026-08-25**

## Как читать этот файл

Этот файл открывается перед каждой рабочей сессией. Он показывает, какой план активен, какие планы закрыты на текущей стадии проектирования, какие ещё открыты и какие проверки не пройдены.

Статус относится к текущей стадии проекта, а не означает, что код соответствующего слоя уже реализован:

- `in_progress` — текущая рабочая область;
- `closed` — планирование области зафиксировано на текущей стадии;
- `open` — план есть, но реализация/следующая проверка ещё не начата;
- `blocked` — работа остановлена по конкретной причине.

## Текущая стадия

- **Стадия:** 3 — операторские правки после live smoke.
- **Активный план:** [37 — operator follow-up](plans/37-operator-follow-up/01-history-station-edit.md).
- **Текущая задача:** история ограничена 10 jobs и раскрывает сохранённые
  target/artifact details; station и TrueNAS mapping редактируются через UI;
  native EXE может bootstrap station без Python и `--report`.
- **Последнее исправление:** добавлены `publish_artifacts`, retention worker и
  allowlisted `pool.dataset.delete`; фактическое удаление закрыто отдельным
  `TRUENAS_CLEANUP_APPLY_ENABLED`. В native EXE исправлено автоматическое
  создание каталогов identity для чистого Windows-ПК; root EXE пересобран.
- **Следующий разрешённый шаг:** проверить обновлённый EXE на Windows-ПК,
  применить две новые Alembic migrations и проверить Compose/UI на одной
  тестовой станции.
- **Запрещено сейчас:** включать cleanup apply или live NAS cleanup без
  отдельного подтверждения оператором; текущие dataset должны оставаться
  защищены от удаления.

## Статус планов

| План | Статус | Чекап текущей стадии | Следующая проверка |
|---|---|---|---|
| [00 — Контекст](plans/00-context.md) | `closed` | `CODEX.md` изучен; границы MVP записаны | обновлять только при изменении требований |
| [01 — Архитектура](plans/01-architecture/01-layers.md) | `closed` | слои, зависимости и package layout сверены с каркасом | сверять при добавлении новых adapters |
| [02 — БД](plans/02-database/01-schema.md) | `closed` | сущности, связи и инварианты описаны | проверить перед первой миграцией |
| [03 — State machine](plans/03-state-machine/01-state-machine.md) | `closed` | состояния и переходы описаны | покрыть переходы unit-тестами |
| [04 — Безопасность](plans/04-security/01-security.md) | `closed` | секреты, audit и Basic Auth зафиксированы | проверить реализацию auth и redaction |
| [05 — API](plans/05-api/01-contract.md) | `closed` | endpoint-контракты описаны | проверить схемы через contract tests |
| [06 — Windows-агент](plans/06-agent/01-windows-agent.md) | `in_progress` | Python runtime сохранён как legacy recovery; native .NET Worker Service, self-contained installer, report, DPAPI/ACL и native SCM добавлены | Windows native LocalSystem/ACL/heartbeat smoke |
| [06.03 — Native .NET agent](plans/06-agent/03-native-dotnet-agent.md) | `in_progress` | Linux build прошёл; native agent поддерживает проверку старого credential и fallback к enrollment | проверить обновлённый exe на клиентском Windows-ПК |
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
| [30 — TrueNAS LAN integration gate](plans/30-truenas-lan-gate/01-local-api-docs-and-connection.md) | `open` | версия/live docs подтверждены; `wss://`-only runtime, TLS CA/verification boundary и auth boundary созданы; JSON-RPC smoke check не выполнялся | настроить доверенный CA или временный LAN TLS smoke |
| [31 — Frontend и база знаний](plans/31-frontend/01-operator-ui-and-knowledge-base.md) | `in_progress` | Vite shell, Basic Auth login, overview, station read/create, station delete/re-register, allowlisted Markdown reader, publish wizard, job read model и client station report prefill созданы; миграция и `/api/v1/stations` проверены | перейти к отдельному TrueNAS/Windows runtime gate |
| [32 — Удаление station и агента](plans/32-station-removal/01-station-removal-and-agent-revocation.md) | `closed` | DELETE Basic Auth route, soft-delete, удаление agent/commands, отзыв token, сохранение истории и повторная регистрация по UUID реализованы и проверены | обновлять только при изменении политики удаления |
| [33 — Automatic onboarding и полный-disk clone](plans/33-bootstrap-and-zfs-workflow/01-provisioning-and-full-disk-clone.md) | `in_progress` | provisioning API/UI, native bootstrap contract, optional admin preflight и `source_dataset` contract добавлены; native publish/Compose smoke ещё впереди | собрать exe, применить migration и проверить client flow |
| [34 — Runtime worker и TrueNAS secret](plans/34-worker-runtime/01-compose-worker-and-secret-boundary.md) | `in_progress` | Compose worker, outbox polling, Dramatiq consumer и fake executor mode добавлены; пользовательский runtime ещё не проверен | pull, rebuild и проверить accepted job по worker logs |
| [35 — История и process policy](plans/35-update-history-and-process-policy/01-history-process-policy.md) | `closed` | история publish, CRUD process rules, экран политики и retry preflight реализованы; `196 passed, 1 skipped`, frontend tests/build и Ruff пройдены | пользовательский Compose/UI smoke |
| [36 — TrueNAS write adapter](plans/36-truenas-write-adapter/01-snapshot-clone-extent-switch.md) | `in_progress` | snapshot → clone → update `device/file` старого extent → association/LUN read-back, station mapping, Dramatiq executor, fake acceptance и TLS runtime boundary добавлены; backend `204 passed, 1 skipped`, Ruff/Compose пройдены | read-only LAN smoke, затем отдельный one-station apply gate |
| [37.01 — История и station edit](plans/37-operator-follow-up/01-history-station-edit.md) | `closed` | history default 10, details read model, `dry_run=false`, PATCH station и mapping edit добавлены; targeted tests прошли | пользовательский UI smoke |
| [37.02 — Native agent EXE](plans/37-operator-follow-up/02-native-agent-exe.md) | `in_progress` | source installer принимает provisioning token без `--report`, identity создаётся native EXE, stdout report сохраняется JSON-only; root EXE пересобран | проверить обновлённый EXE на Windows |
| [37.03 — Dataset retention](plans/37-operator-follow-up/03-dataset-retention.md) | `in_progress` | `publish_artifacts`, migration, cleanup use case, Dramatiq schedule и TrueNAS delete allow-list добавлены; apply gate выключен | применить migration и сделать dry-run cleanup в Compose |

## Чекап решений

- [x] Worker: **Dramatiq**.
- [x] Broker для Dramatiq: Redis, согласно исходной архитектуре.
- [x] Авторизация приложения: **HTTP Basic Auth**.
- [x] Логин приложения: `admin`.
- [x] Пароль приложения не хранится в репозитории; runtime-конфигурация — `BASIC_AUTH_PASSWORD`.
- [x] TrueNAS API key остаётся отдельным backend/worker secret и не связан с Basic Auth приложения.
- [x] TrueNAS API key передаётся только через `wss://`; проверка TLS включена по умолчанию, CA задаётся через `TRUENAS_TLS_CA_FILE`.
- [x] Официальная документация TrueNAS найдена и занесена в [docs/ONLINE_DOCS.md](docs/ONLINE_DOCS.md).
- [x] Проверить фактическую версию `25.10.5` и live `/api/docs/current/` конкретного NAS через временный доступ; runtime smoke check отдельно.
- [x] Автоматическая проверка версии игры через `game_version_marker` не входит в MVP; факт обновления подтверждает оператор.
- [x] Публикация относится к полному исходному dataset/диску, например `games/master-games`; отдельная сущность игры не является источником TrueNAS-операции.
- [x] Admin station не обязательна: Controller UI остаётся control plane, клиентские станции — targets, TrueNAS выполняет snapshot/clone.
- [x] Для автоматического onboarding используется отдельный короткоживущий provisioning token; Basic Auth оператора в native agent не передаётся.
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
- [x] Alembic config подключён; baseline revision `bee81bac70cc` сгенерирована, миграции не применялись.
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
- [x] Server-agent heartbeat contract: protocol `1`, hostname/IP/MAC validation and persistence; baseline migration сгенерирована, apply не выполнялся.
- [x] Общий набор тестов после agent/server contract slice: `125 passed, 1 skipped` на Python 3.12/uv.
- [x] Protected credential boundary: `CredentialProtector` через `Protocol`, atomic protected-byte store и DPAPI machine-scope adapter для LocalSystem; plaintext fallback не используется автоматически.
- [x] Общий набор тестов после protected credential slice: `131 passed, 1 skipped` на Python 3.12/uv.
- [x] Windows Service boundary: thread-safe stop bridge, optional pywin32 SCM wrapper и platform-specific dependency; Windows SCM runtime не запускался.
- [x] Общий набор тестов после service wrapper slice: `133 passed, 1 skipped` на Python 3.12/uv.
- [x] Windows credential ACL boundary: ACL накладывается на temporary blob до atomic replace; platform factory fail-closed без explicit dev fallback.
- [x] Общий набор тестов после ACL slice: `136 passed, 1 skipped` на Python 3.12/uv.
- [x] Signed agent command flow: Ed25519 envelope, operator issue route, heartbeat lease/retry, local dedupe и Bearer acknowledgement route.
- [x] Agent command public-key config field and external base64 verifier boundary added.
- [x] Agent runtime composition wires public-key verifier, collectors, HTTPS transport and command refresh callback; Windows runtime не запускался.
- [x] Agent entrypoint loads enrolled credential and builds `PyWin32ServiceRuntime`; SCM commands не запускались.
- [x] Explicit one-shot enrollment command проверяет `AGENT_UUID`/token, использует
  injected Protocol boundaries и не выводит credential/token; deployment notes
  добавлены в `docs/AGENT_DEPLOYMENT.md`.
- [x] Пошаговая Windows staging-инструкция добавлена в
  `docs/AGENT_INSTALL.md`; installer orchestration добавлен, но фактический
  LocalSystem/ACL runtime по-прежнему не проверялся.
- [x] SCM install/start path не расшифровывает DPAPI credential под оператором:
  загрузка deferred до фактического запуска службы под LocalSystem.
- [x] Быстрый onboarding Windows-клиента: stdlib-only
  `scripts/agent_station_report.py` сохраняет стабильный UUID, выводит JSON
  station/agent/network/drive данных и не содержит секретов.
- [x] Единый installer orchestration: копирует release checkout, запускает
  locked `uv` dependencies, вводит token обычным prompt, не кладёт token
  в machine environment/argv и регистрирует SCM service под текущей account.
- [x] `AGENT_COMMAND_VERIFY_KEY` сделан необязательным для установки: без него
  heartbeat работает, а подписанные refresh-команды отключены.
- [x] Windows ACL runtime hardening: named protected DACL, безопасный код
  Windows-ошибки и preflight DPAPI/ACL до расходования enrollment token.
- [x] Windows installer SCM boundary: регистрация и запуск службы выполняются
  target `.venv` Python с pywin32; внешний `py -3` больше не импортирует
  `win32service`, пароль передаётся через stdin.
- [x] Windows installer регистрирует службу LocalSystem без пароля, использует
  machine-scope DPAPI и мигрирует старый user-scope credential без нового token.
- [x] Native .NET Worker Service добавлен как рекомендуемый runtime: config в
  `agent.json`, native SCM API, видимый token prompt, report и self-contained
  `win-x64` publish path; Linux build прошёл.
- [x] Native installer больше не пропускает enrollment только из-за наличия
  старого `agent.credential`: binding проверяется heartbeat, при `401`
  запрашивается новый token.
- [x] SCM process не читает environment/DPAPI до входа в dispatcher; credential
  и AgentService создаются внутри `SvcDoRun`, а `debug`/`foreground` используют
  консольный режим без pywin32 `pythonservice.exe`.
- [x] Native Windows smoke подтверждён оператором: report/enrollment выполнены,
  station online, heartbeat свежий; native служба запущена на клиентском ПК.
- [ ] Проверить отдельный compatibility path обновления старой Python-установки
  и чтения старого machine-scope credential native агентом.
- [x] Frontend принимает station report, валидирует allowlisted JSON, заполняет
  поля создания station и напоминает оператору о раздельной передаче one-shot
  enrollment token.
- [x] Plan 31 frontend: React/Vite shell, in-memory Basic Auth login, status
  explanations, station read/create и Markdown knowledge reader созданы.
- [x] Frontend design layer: подключён lucide-react; повторяемые
  StatusBadge, MetricCard, SectionHeading, HelpHint и InfoNote вынесены в
  presentation/components/ui.tsx; декоративные текстовые иконки заменены на
  Lucide.
- [x] Publish wizard slice: добавлены backend prepare/dispatch routes и
  frontend flow draft → server preflight → operator confirmation → outbox
  dispatch; offline/stale stations disabled, unknown/block не обходятся UI.
- [x] Publish read model slice: frontend polling GET job read model показывает
  общий и per-target progress; completed/partial_failure/failed и
  recovery_required отображаются только по данным backend.
- [x] Общий набор проверок после publish presentation/frontend slice:
  156 passed, 1 skipped; Ruff check/format и frontend npm run build прошли.
- [x] Frontend production build и visual smoke-check login подтверждены:
  npm run build прошёл, headed browser check не показал ошибок; backend/API
  runtime в этой проверке не запускался.
- [x] Frontend build: `npm run build` прошёл; headed visual smoke-check login
  пройден, backend/API runtime не запускался в рамках frontend build.
- [x] Frontend key tests: `npm run test` — 3 test files, 4 tests passed;
  проверены Basic Auth/error mapping, station selection и knowledge allowlist.
- [x] Station removal slice: DELETE Basic Auth route, подтверждение в UI,
  отзыв token, удаление agent/commands, сохранение snapshots и повторная
  регистрация по тому же стабильному UUID проверены ключевыми тестами.
- [x] После station removal slice: backend targeted tests `20 passed`, frontend
  tests `7 passed`, `npm run build` и Ruff check/format прошли.
- [x] Compose config: `docker compose config` прошёл с тестовыми переменными;
  backend startup теперь выполняет idempotent `alembic upgrade head` до Uvicorn.
- [x] Compose runtime: PostgreSQL baseline migration `bee81bac70cc` применена,
  `stations`/`publish_jobs` созданы, backend healthy и `/api/v1/stations`
  вернул `200` через Basic Auth.
- [x] Исправлен Windows CRLF-регресс в Docker backend entrypoint: `.gitattributes`
  фиксирует LF для shell-файлов, Dockerfile нормализует скрипт; backend image
  собран, migration и `/openapi.json` проверены в Compose.
- [x] Добавлена fail-fast проверка Alembic revision: Docker build не проходит
  без migration-файла, а entrypoint не запускает API после ошибки `upgrade head`.
- [x] Authorized visual smoke-check: временный SQLite backend и headed browser
  подтвердили login, health, stations, publish wizard и knowledge base; артефакты
  вынесены из workspace в `/tmp/tnas-playwright-artifacts`.
- [x] Общий набор тестов после command delivery/runtime/enrollment slice: `153 passed, 1 skipped` на Python 3.12/uv.
- [x] Redis broker execution и настоящий TrueNAS не запускались.
- [x] Найдена и исправлена причина accepted job на `0%`: в Compose отсутствовал
  runtime worker/relay; добавлен отдельный `worker` service.
- [x] `TRUENAS_API_KEY` добавлен в Compose worker environment как внешний secret;
  fake executor его не использует, а write-capable adapter включается только
  отдельным `TRUENAS_APPLY_ENABLED=true` gate.
- [ ] Compose worker реально запущен на пользовательском админском ПК и
  обработал новую publish job.
- [ ] Повторно проверить worker после исправления asyncpg event-loop и
  embedded Prometheus middleware на пользовательском ПК.
- [x] Provisioning token domain/repository/UoW, migrations, Basic Auth issue route, bootstrap route, native client contract и UI button добавлены; backend `181 passed`, frontend `7 passed`, build/Ruff пройдены.
- [ ] Обновлённый native exe опубликован и проверен на Windows-клиенте с автоматическим созданием station.
- [ ] Alembic migrations `7f5d0f1c9b42`/`8a9c2d7e4f11` применены в пользовательском Compose runtime.
- [ ] Реальный TrueNAS snapshot/clone apply не выполнялся; нужен отдельный согласованный write gate.
- [ ] История publish и web process policy реализуются по плану 35.
- [x] История publish и web process policy реализованы по плану 35.
- [x] TrueNAS adapter обновляет `device/file` старого extent, не создаёт новый extent.
- [x] Worker wiring, fake read-back и station target mapping реализованы.
- [x] TLS runtime boundary: `wss://`-only URL, trimming secret, CA/verification options и безопасные TLS/WebSocket ошибки покрыты тестами.
- [x] Локальный полный чек-ап: backend `204 passed, 1 skipped`, frontend `8 passed`, production build, Ruff, format и compileall пройдены.
- [ ] One-station live apply на NAS выполнен: snapshot и clone созданы, но
  `iscsi.extent.update` не подтверждён read-back и target получил
  `recovery_required`; созданный clone не удалять и job вслепую не повторять.
- [x] Исправлен формат TrueNAS DISK/ZVOL mapping: API получает
  `disk=zvol/<dataset>`, read-only mapper выбирает `disk` для `DISK`, а
  recovery сохраняет безопасную первичную причину ошибки.

## Принятое решение по версии игры

Автоматически определять, обновилась ли игра, не требуется. Оператор отвечает за
подтверждение факта обновления; backend проверяет только технический результат
workflow: состояние агента, доступность `D:` и соответствие target/mapping.

`game_version_marker` удалён из текущего agent payload, domain snapshot, API,
хранилища и baseline migration, поэтому он не создаёт отдельной настройки игры
и не является gate для publish/verify.

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
| 2026-08-23 | Убран автоматический `game_version_marker` | Версию игры подтверждает оператор; приложение не поддерживает дополнительную game-specific настройку |
| 2026-08-23 | Добавлен локальный Compose-контур и frontend key tests | PostgreSQL/Redis/backend/frontend описаны; Basic Auth, selection и knowledge allowlist проверены |
| 2026-08-24 | Исправлен PostgreSQL boolean default в baseline migration | `dry_run/allow_hot_switch` переведены с SQLite `1/0` на SQL `TRUE/FALSE`; Compose startup migration и stations API проверены |
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
| 2026-08-23 | Добавлена граница защищённого credential storage | DPAPI user-scope adapter и fake-protector tests; реальный Windows/SCM runtime не запускался |
| 2026-08-23 | Добавлена Windows Service boundary | `WindowsServiceHost`, pywin32 SCM adapter и Windows-only dependency; регистрация службы и Windows runtime не запускались |
| 2026-08-23 | Добавлена Windows credential ACL boundary | pywin32 ACL adapter вызывается до atomic replace; фактическая service account/installer проверка не запускалась |
| 2026-08-23 | Добавлен plan 06.02 и signed command delivery boundary | Ed25519, lease/retry, local dedupe и ack; baseline migration оставлена production gate |
| 2026-08-23 | Замкнут agent runtime composition | `AGENT_COMMAND_VERIFY_KEY`, verifier, collectors, HTTPS transport и safe refresh callback собраны без Windows/network runtime |
| 2026-08-23 | Сгенерирована Alembic baseline revision `bee81bac70cc` | Включены текущие таблицы и `agent_commands`; migration не применялась, PostgreSQL не подключался |
| 2026-08-23 | Добавлен agent entrypoint | Protected credential loading и `PyWin32ServiceRuntime` composition; реальные SCM install/start/stop не выполнялись |
| 2026-08-23 | Добавлен explicit one-shot agent enrollment command | `AGENT_UUID`/token проходят через runtime environment, credential сохраняется защищённо; controller, SCM и migration не запускались |
| 2026-08-23 | Добавлена Windows staging-инструкция | Зафиксированы controller enrollment, DPAPI/service account порядок, SCM-команды и smoke checks; фактическая Windows-проверка не выполнялась |
| 2026-08-25 | Добавлен план 33 | Provisioning token автоматически создаёт station/agent; admin station сделана optional; publish terminology переведена с `game_name` на `source_dataset` для полного диска |
| 2026-08-23 | Исправлен SCM credential lifecycle | `install`/`start` не требуют расшифровки под администратором; credential загружается при `SvcDoRun` под service account |
| 2026-08-23 | Начат план 31 frontend | Добавлены React/Vite shell, in-memory Basic Auth, station read/create и Markdown knowledge base; полный workflow отложен на следующие подшаги |
| 2026-08-23 | Продолжен план 31 frontend | Подключён lucide-react, добавлены reusable UI-компоненты и подтверждены production build/visual login smoke-check |
| 2026-08-23 | Продолжен plan 31 publish slice | Замкнуты prepare/dispatch HTTP-контракты и frontend wizard; worker/TrueNAS completion не симулируется |
| 2026-08-23 | Продолжен plan 31 read model slice | Добавлен polling publish job, per-target progress и безопасные terminal/recovery состояния |
| 2026-08-24 | Добавлен быстрый Windows-agent onboarding | Клиентский stdlib-only script собирает station report; frontend валидирует JSON и заполняет форму создания station без передачи Basic Auth или credential |
| 2026-08-24 | Добавлен единый Windows installer orchestration | Скрипт копирует release checkout, ставит locked dependencies, выполняет enrollment и регистрирует службу; реальный Windows/SCM smoke оставлен отдельным gate |
| 2026-08-24 | Упрощён первый запуск агента | Verify key больше не требуется; общий station/agent UUID берётся из station report, token вводится открыто, пароль service account остаётся скрытым |
| 2026-08-24 | Добавлен план 32 и удаление station/agent | DELETE soft-delete скрывает станцию, удаляет agent binding и pending commands, отзывает tokens, сохраняет историю; тот же station report UUID можно использовать для повторной регистрации |
| 2026-08-24 | Исправлен Windows ACL gate | named protected DACL, SID текущего process token, диагностируемый Windows error code и локальный DPAPI/ACL preflight до расходования enrollment token; native Windows retest остаётся открытым |
| 2026-08-24 | Исправлен `win32service` installer gate | SCM registration/start перенесены в target `.venv` с pywin32; пароль service account передаётся через stdin, внешний `py -3` больше не импортирует `win32service` |
| 2026-08-24 | Уточнён Windows service password gate | пустой пароль отклоняется до SCM-регистрации; Basic Auth отделён от пароля входа Windows; добавлены подсказки для ошибок `1069` и `1385` |
| 2026-08-24 | Переведён Windows agent на LocalSystem | удалён prompt пароля, включён machine-scope DPAPI, ACL для SYSTEM/Administrators и миграция старого user-scope credential |
| 2026-08-25 | Добавлен native .NET Windows agent | устранение Python/pywin32 SCM проблем: self-contained Worker Service, native SCM, deferred startup, DPAPI/ACL и совместимый report; Windows smoke остаётся открытым |
| 2026-08-25 | Добавлен план 34 и Compose worker runtime | accepted job сохранялась в outbox, но relay и Dramatiq consumer не запускались; TrueNAS API key пока не используется fake executor |
| 2026-08-25 | Исправлен worker event-loop/runtime middleware | `asyncio.run` с общим asyncpg pool давал `Future attached to a different loop`; embedded Worker также не инициализировал Prometheus через CLI hook |
| 2026-08-25 | Исправлен порядок Dramatiq actor/consumer | actor объявлялся до embedded `Worker.start()`, поэтому outbox dispatch проходил, но consumer очереди не создавался |
| 2026-08-25 | Исправлен terminal state для dry-run | симулированный target доходил до 100%, но job оставалась `publishing`; теперь сохраняется `completed` с причиной `dry_run_simulation` |
| 2026-08-25 | Добавлены планы 35–36 | после симуляции начаты история/process gate и controlled TrueNAS adapter |
| 2026-08-25 | Уточнён TrueNAS extent workflow | по фактической схеме пользователя association сохраняется, а старый extent получает новый `device/file` через `iscsi.extent.update` |
| 2026-08-25 | Завершён план 35 | добавлены update history, CRUD process policy, экран политики и retry preflight; `196 passed, 1 skipped` |
| 2026-08-25 | Продолжен план 36 | добавлен fail-closed write adapter для snapshot/clone и обновления старого extent без targetextent switch |
| 2026-08-25 | Подключён план 36 к worker | добавлены TrueNAS workflow, station target mapping, fake read-back и режим `PUBLISH_EXECUTOR_MODE=truenas`; реальный NAS не запускался |
| 2026-08-25 | Завершён локальный чек-ап плана 36 | backend `203 passed, 1 skipped`, frontend `8 passed`, production build, Ruff, format и compileall пройдены; следующий шаг — read-only LAN smoke |
| 2026-08-25 | Исправлен TrueNAS TLS runtime | `ws://` запрещён для API key, добавлены `wss://`, CA/verification settings и диагностируемые TLS/WebSocket ошибки; реальный NAS не запускался |
| 2026-08-25 | Исправлен live extent switch после one-station теста | TrueNAS API использует `disk=zvol/...`, а `/dev` добавляется middleware; обновлены adapter, read-back, fake/fixtures и инструкция, recovery теперь сохраняет причину исходного сбоя |
| 2026-08-25 | Добавлен план 37 operator follow-up | История ограничена 10 jobs, добавлены details, station/mapping edit и default `dry_run=false` |
| 2026-08-25 | Добавлен реестр publish artifacts и retention worker | Создана migration, Dramatiq schedule и отдельный fail-closed TrueNAS `pool.dataset.delete`; apply gate выключен по умолчанию |
| 2026-08-25 | Native installer упрощён | `--report` стал необязательным, identity и bootstrap выполняются self-contained EXE без Python; root EXE требует пересборки из обновлённого source |
| 2026-08-25 | Локальный чек-ап плана 37 | `213 passed, 1 skipped`, Ruff/format/compileall, Alembic head, frontend `8 passed` и production build; реальный NAS cleanup и Windows smoke не выполнялись |
