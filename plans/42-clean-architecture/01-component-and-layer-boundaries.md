# План 42. Разделение компонентов и чистая архитектура

## Цель

Привести репозиторий к явной структуре монорепозитория с тремя независимо
собираемыми продуктами:

- `backend` — Controller API, background worker и интеграции;
- `frontend` — React/Vite интерфейс оператора;
- `winclient` — основной native .NET Windows Agent и изолированный legacy
  Python client на переходный период.

Backend обязательно разделяется на `presentation`, `application`,
`infrastructure`, `domain`. Зависимости направлены внутрь, framework и IO код не
попадает в domain/application, а frontend и winclient не импортируют backend
модули. План описывает физический перенос без одновременного изменения
поведения, затем вводит автоматические архитектурные проверки.

## Входы и зависимости

- архитектурные правила `CODEX.md` и `PROJECT_RULES.md`;
- активный reliability-план 41;
- текущие root packages `domain`, `application`, `presentation`, `repository`,
  `truenas_adapter`, `worker`, `agent`;
- `main.py`, Alembic, Dockerfile/Compose и scripts как текущие entrypoints;
- существующий `frontend/src/{domain,application,presentation}`;
- текущий `windows-agent` с одним `.csproj` и каталогами Domain/Application/
  Infrastructure;
- полный Python, frontend и native agent test/build baseline.

## Найденные архитектурные проблемы

1. Backend и Python Windows client находятся рядом в корне и используют общие
   top-level imports, поэтому граница продуктов не выражена файловой структурой.
2. `repository`, `truenas_adapter` и `worker` являются infrastructure adapters,
   но оформлены как равноправные корневые слои.
3. Root `main.py` одновременно знает FastAPI, SQLAlchemy, TrueNAS, commands,
   queue и client signing implementation.
4. Backend импортирует `Ed25519CommandSigner` из `agent`, то есть server зависит
   от реализации Windows-клиента.
5. Legacy Python agent импортирует backend `domain.snapshot` и
   `domain.agent_command`; изменение server domain может сломать клиентский EXE.
6. Application ports собраны в одном большом `application/ports.py`, а TrueNAS
   DTO и publish orchestration распределены между несколькими модулями без
   feature boundaries.
7. FastAPI routes всех областей собраны в одном `presentation/http.py`, что
   затрудняет независимую проверку station, agent, publish и cleanup slices.
8. Frontend HTTP client находится в `application/api`, хотя `fetch`, Basic Auth
   и transport error mapping относятся к infrastructure.
9. Frontend pages напрямую координируют запросы, retry и polling; application
   use cases/ports выражены только частично.
10. Native .NET agent имеет папки слоёв, но один `.csproj` разрешает любые
    обратные ссылки. `Application/AgentWorker` создаёт concrete infrastructure
    объекты напрямую.
11. Root Python dependency set одновременно содержит FastAPI/SQLAlchemy/Dramatiq
    и legacy Windows dependencies (`psutil`, `pywin32`), поэтому backend image и
    client release не имеют независимых dependency boundaries.
12. Тесты зеркалят старые каталоги, но не проверяют запрещённые импорты. SQLite
    suite не доказывает корректность PostgreSQL infrastructure.

## Целевая структура

```text
tnas/
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── src/tnas_controller/
│   │   ├── domain/
│   │   │   ├── station/
│   │   │   ├── agent/
│   │   │   ├── publish/
│   │   │   └── shared/
│   │   ├── application/
│   │   │   ├── station/
│   │   │   ├── agent/
│   │   │   ├── preflight/
│   │   │   ├── publish/
│   │   │   ├── cleanup/
│   │   │   └── ports/
│   │   ├── infrastructure/
│   │   │   ├── persistence/sqlalchemy/
│   │   │   ├── messaging/dramatiq/
│   │   │   ├── truenas/jsonrpc/
│   │   │   ├── security/
│   │   │   ├── config/
│   │   │   └── observability/
│   │   ├── presentation/
│   │   │   └── http/
│   │   │       ├── routers/
│   │   │       ├── schemas/
│   │   │       ├── auth/
│   │   │       └── errors/
│   │   └── bootstrap/
│   │       ├── api.py
│   │       └── worker.py
│   ├── migrations/
│   └── tests/
│       ├── unit/{domain,application}/
│       ├── integration/{persistence,messaging,truenas}/
│       ├── contract/{http,agent,truenas}/
│       └── acceptance/
├── frontend/
│   ├── src/
│   │   ├── domain/
│   │   ├── application/{ports,use-cases}/
│   │   ├── infrastructure/{http,content,storage}/
│   │   ├── presentation/{components,pages,hooks}/
│   │   └── main.tsx
│   └── tests/
├── winclient/
│   ├── native/
│   │   ├── TrueNasController.Agent.sln
│   │   ├── src/
│   │   │   ├── Agent.Domain/
│   │   │   ├── Agent.Application/
│   │   │   ├── Agent.Infrastructure/
│   │   │   └── Agent.Host/
│   │   └── tests/
│   ├── legacy-python/
│   │   ├── pyproject.toml
│   │   ├── src/tnas_agent/
│   │   └── tests/
│   ├── installers/
│   └── artifacts/                 # release output, не source of truth
├── contracts/                     # data-only OpenAPI/agent protocol fixtures
├── deploy/
│   ├── compose.yaml
│   └── docker/
├── docs/
├── plans/
└── scripts/                       # только repo-level development tools
```

`bootstrap` — только composition root и process entrypoints. Это не пятый
бизнес-слой: он импортирует concrete adapters и связывает их с ports, но не
содержит use cases, SQL queries или policy.

## Правила backend-слоёв

### `domain`

- Entities, value objects, enums, state transitions и чистые domain services.
- Только Python stdlib и собственный domain; никаких FastAPI, Pydantic,
  SQLAlchemy, Dramatiq, Redis, HTTP/WebSocket, filesystem или environment.
- Domain не знает ORM records, API schemas, JSON field names и worker payload.
- Инварианты, общие для API, worker и tests, выражаются здесь.

### `application`

- Один use case — одна операция пользователя или worker stage.
- Commands/results являются framework-free dataclasses/value objects.
- Ports находятся рядом с feature либо в `application/ports`; порт принадлежит
  коду, который его вызывает.
- Application импортирует только domain и application. Он не импортирует
  `infrastructure`, `presentation`, SQLAlchemy, FastAPI, Dramatiq или concrete
  JSON-RPC client.
- Transaction boundary, idempotency orchestration, preconditions и durable
  workflow plan принадлежат application. SQL и transport retry mechanism — нет.

### `infrastructure`

- Реализует application ports: SQLAlchemy repositories/UoW, Alembic, Redis/
  Dramatiq, TrueNAS JSON-RPC, cryptography, config и logging/metrics adapters.
- Может импортировать application ports/types и domain, но domain/application
  никогда не импортируют infrastructure.
- SQLAlchemy models не считаются domain entities. Mapping между ORM и domain
  выполняется внутри persistence adapter.
- Worker actor является transport adapter: валидирует envelope, создаёт fresh
  scope/UoW и вызывает application use case.
- TrueNAS method names, retry transport и credentials остаются только здесь.

### `presentation`

- FastAPI routers, HTTP/WebSocket schemas, auth dependency, status/error mapping.
- Presentation импортирует application API и необходимые domain value types.
- Не импортирует infrastructure/repositories и не создаёт concrete clients.
- Router не содержит SQL, TrueNAS calls, транзакционную policy или долгий
  workflow. Один router соответствует feature area.

### `bootstrap`

- `api.py` и `worker.py` создают config, engine, broker, adapters и use cases.
- Допустимо импортировать все backend-слои только здесь.
- Entry point остаётся тонким и проверяется composition smoke test.

## Матрица разрешённых зависимостей

| Источник | Разрешённые внутренние зависимости |
|---|---|
| backend `domain` | backend `domain` |
| backend `application` | backend `application`, `domain` |
| backend `presentation` | backend `presentation`, `application`, `domain` |
| backend `infrastructure` | backend `infrastructure`, `application`, `domain` |
| backend `bootstrap` | все backend-слои |
| frontend `domain` | frontend `domain` |
| frontend `application` | frontend `application`, `domain` |
| frontend `infrastructure` | frontend `infrastructure`, `application`, `domain` |
| frontend `presentation` | frontend `presentation`, `application`, `domain` |
| frontend `main.tsx` | все frontend-слои |
| winclient `Domain` | winclient `Domain` |
| winclient `Application` | winclient `Application`, `Domain` |
| winclient `Infrastructure` | winclient `Infrastructure`, `Application`, `Domain` |
| winclient `Host` | все winclient-слои |

Между `backend`, `frontend` и `winclient` запрещены source imports и общие
runtime packages. Они взаимодействуют только через versioned HTTP/JSON
контракты. `contracts/` хранит data-only OpenAPI schema и зафиксированные JSON
fixtures; он не является импортируемой общей domain-моделью.

## Карта переноса текущего кода

| Сейчас | Цель |
|---|---|
| `domain/` | `backend/src/tnas_controller/domain/` |
| `application/` | `backend/src/tnas_controller/application/` с разбиением по feature |
| `presentation/` | `backend/src/tnas_controller/presentation/http/` |
| `repository/` | `backend/src/tnas_controller/infrastructure/persistence/sqlalchemy/` |
| `repository/migrations/` | `backend/migrations/` |
| `truenas_adapter/` | `backend/src/tnas_controller/infrastructure/truenas/jsonrpc/` |
| `worker/` | adapters в `infrastructure/messaging/dramatiq/`, entrypoint в `bootstrap/worker.py` |
| `main.py` | `backend/src/tnas_controller/bootstrap/api.py` |
| server command signer из `agent/` | `backend/.../infrastructure/security/` |
| `tests/{domain,application,...}` | `backend/tests/{unit,integration,contract,acceptance}` |
| `frontend/src/application/api/` | port в `application/ports`, fetch adapter в `infrastructure/http/` |
| `frontend/src/application/knowledge/` | port/use case в application, Markdown adapter в `infrastructure/content/` |
| `windows-agent/` | `winclient/native/` с отдельными projects |
| `agent/` | `winclient/legacy-python/src/tnas_agent/` |
| `tests/agent/` | `winclient/legacy-python/tests/` |
| `scripts/install_windows_agent.py` и service scripts | `winclient/legacy-python/installers/` |
| root `TrueNasControllerAgent.exe` | versioned release artifact; не импортируемый source |
| `Dockerfile`, `docker/`, `docker-compose.yml` | `backend/Dockerfile` и `deploy/` |

## Feature boundaries backend

Внутри domain/application код группируется по предметным областям, а не по
типу файла:

- `station` — registry, edit/remove и storage binding;
- `agent` — provisioning, enrollment, heartbeat, command delivery;
- `preflight` — process rules, snapshot freshness и wizard gate;
- `publish` — draft, confirmation, dispatch, checkpoints, switch, verify,
  rollback и read model;
- `cleanup` — dataset inventory, reconciliation и retention;
- `shared` — только действительно общие UUID/time/error primitives.

Запрещён общий `utils.py`, универсальный `Manager`, circular imports между
features и перенос transport DTO в domain. Если двум features нужен контракт,
его владелец определяется по use case; зависимость идёт через небольшой port.

## Frontend

- Domain содержит типы и чистые функции сортировки/state rules без React,
  browser API и transport field parsing.
- Application содержит сценарии экрана, ports (`ControllerGateway`,
  `KnowledgeSource`, clock/id generator) и состояния операций.
- Infrastructure реализует ports через `fetch`, Basic Auth session, Markdown
  imports и browser storage. HTTP DTO преобразуются в frontend domain models.
- Presentation содержит React pages/components/hooks и вызывает application
  services; страницы не конструируют URL, headers, idempotency/retry policy.
- `main.tsx` является composition root и передаёт concrete adapters.
- TypeScript aliases и lint boundary запрещают обратные импорты. UI не получает
  backend secrets и не разделяет с backend source package.

## Winclient

### Native .NET — основной client

- `Agent.Domain` — snapshot/command/identity value objects без HTTP, DPAPI,
  Windows Service и `Microsoft.Extensions`.
- `Agent.Application` — heartbeat/enrollment/command use cases и ports для
  controller gateway, snapshot collector, credential store, clock и delay.
- `Agent.Infrastructure` — HttpClient, JSON contracts, DPAPI/ACL, process/drive
  collectors, Ed25519 verifier, filesystem и SCM adapters.
- `Agent.Host` — CLI, Windows Service host, DI и composition root.
- Каждый слой получает отдельный `.csproj`; ProjectReference физически
  разрешает только направление внутрь.
- `AgentWorker` перестаёт создавать `ControllerClient`, collector и credential
  store; зависимости передаются через ports/DI.

### Legacy Python — временный client

- Получает собственный `pyproject.toml`, package namespace и lockfile.
- Не импортирует backend domain/application. Его protocol DTO принадлежат
  клиенту и проверяются server contract fixtures.
- Installer и Windows service scripts находятся внутри legacy component.
- Поддерживается только для upgrade/recovery до подтверждённого rollout native
  agent. Удаление legacy client оформляется отдельным решением после проверки
  совместимости credentials и установки.

## Конфигурация, зависимости и контракты

- Backend и legacy client получают независимые dependency manifests/lockfiles.
  Backend image не устанавливает `pywin32`/`psutil`, winclient не устанавливает
  FastAPI/SQLAlchemy/Dramatiq.
- Environment parsing централизован в infrastructure config, но secrets
  передаются в adapters только composition root.
- HTTP API version остаётся `/api/v1` во время физического переноса.
- OpenAPI snapshot фиксируется в contract tests. Native и legacy clients имеют
  fixtures для enrollment, heartbeat, commands и error responses.
- Database table/revision names и JSON payload не меняются только ради новых
  путей. Поведенческие schema changes выполняются планом 41 отдельными commits.
- Compose service names, healthchecks и external env names сохраняются до
  отдельного deploy migration step.

## Последовательность реализации

### 42.1. Зафиксировать границы и baseline

- [ ] Снять полный test/build/Compose/Alembic baseline и карту импортов.
- [ ] Добавить backend import contracts, frontend import restrictions и .NET
  project dependency tests, сначала в режиме отчёта.
- [ ] Зафиксировать OpenAPI и agent protocol fixtures до перемещения.
- [ ] Убедиться, что apply/cleanup flags выключены.

**Gate:** baseline воспроизводим, запрещённые текущие связи перечислены, ни один
runtime path не изменён.

### 42.2. Отделить backend core

- [ ] Создать installable `backend/src/tnas_controller` package.
- [ ] Через `git mv` перенести domain без изменений поведения.
- [ ] Перенести application, разбить ports по feature и убрать circular imports.
- [ ] Перенести server command signing из client component в backend
  infrastructure security.
- [ ] Обновить только imports/tests; не совмещать перенос с plan 41 behavior.

**Gate:** domain/application unit tests проходят; domain imports только stdlib,
application не импортирует concrete adapters.

### 42.3. Собрать backend adapters и presentation

- [ ] Перенести repository/Alembic в infrastructure persistence.
- [ ] Перенести TrueNAS adapter в infrastructure truenas.
- [ ] Разделить worker на Dramatiq adapter и `bootstrap/worker.py`.
- [ ] Разбить монолитный FastAPI router по feature и перенести schemas/errors.
- [ ] Создать `bootstrap/api.py`; presentation не импортирует infrastructure.

**Gate:** API, worker, migrations и TrueNAS fake contracts проходят из нового
package; старые top-level packages больше не являются source of truth.

### 42.4. Перенести backend runtime/deploy

- [ ] Выделить backend dependencies и lock strategy.
- [ ] Обновить Dockerfile, Compose contexts/commands, Alembic paths и scripts.
- [ ] Сохранить service names, env contract, volume и startup migration order.
- [ ] Проверить backend/worker images, health endpoint и fake pipeline.

**Gate:** `docker compose config`, image build, migration
upgrade/downgrade/upgrade и fake worker acceptance проходят без legacy root
imports.

### 42.5. Довести frontend до слоёв

- [ ] Выделить application ports/use cases для station, publish, cleanup и
  knowledge flows.
- [ ] Перенести `fetch`/Basic Auth/Markdown/browser adapters в infrastructure.
- [ ] Оставить React, polling hooks и rendering в presentation.
- [ ] Добавить aliases и обязательную проверку import boundaries.

**Gate:** frontend tests/build проходят, presentation не знает HTTP URL/headers,
domain не импортирует React/browser/transport.

### 42.6. Разделить winclient

- [ ] Перенести native agent в `winclient/native` и разделить на четыре
  `.csproj` плюс tests.
- [ ] Вынести interfaces из concrete `AgentWorker`, собрать dependencies в Host.
- [ ] Перенести Python client/installers в `winclient/legacy-python`, удалить
  runtime imports backend packages и дать ему отдельные dependencies.
- [ ] Обновить release scripts/docs; сохранить service name, config paths,
  DPAPI scope и upgrade compatibility.

**Gate:** native build/tests и legacy client tests проходят независимо;
backend не нужен для сборки client, кроме contract fixtures.

### 42.7. Удалить переходные пути

- [ ] Удалить старые root packages/import shims только после зелёных component
  builds и контролируемого дренирования старых worker messages.
- [ ] Удалить дублирующие config/build файлы и root binary из source layout.
- [ ] Обновить CODEX, PROJECT_RULES, README, docs и STATE окончательными paths.
- [ ] Сделать architecture checks обязательными в локальном check и CI.

**Gate:** поиск старых imports/paths пуст, каждый компонент собирается и
тестируется отдельной командой, общий acceptance проходит через публичные
контракты.

## Порядок относительно плана 41

1. Сначала полностью выполнить локальные и PostgreSQL этапы 41.1–41.7 при
   выключенном apply. Архитектурный перенос не смешивается с исправлением
   опасных publish/cleanup/enrollment сценариев.
2. После отдельного reliability acceptance выполнить 42.1–42.4 как
   behavior-preserving перенос backend.
3. Затем выполнить 42.5–42.6 для frontend и winclient, сохраняя уже принятые
   HTTP/agent contracts плана 41.
4. Завершить 42.7, повторить общий acceptance из плана 41 и только после этого
   разрешать следующий live one-station gate.

## Архитектурные проверки

- Backend: import contract запрещает `domain -> application/infrastructure/
  presentation`, `application -> infrastructure/presentation`, `presentation ->
  infrastructure` и cross-component imports.
- Frontend: lint/import graph запрещает domain/application зависеть от React,
  `fetch` и presentation/infrastructure в обратном направлении.
- Winclient: отдельные project references делают обратные зависимости ошибкой
  компиляции; architecture test проверяет namespaces и concrete dependencies.
- Repo: `rg` не находит старые top-level imports после contract phase.
- Contract: OpenAPI/agent fixtures проверяют совместимость без shared source.
- Runtime: API, worker и agents запускаются из собственных component manifests.

## Стратегия коммитов

- Один commit на механический перенос одного слоя/компонента.
- Отдельные commits для import/config fixes, без скрытого изменения поведения.
- Миграции БД и plan 41 behavior не смешиваются с `git mv`.
- После каждого commit запускаются тесты затронутого компонента и architecture
  checks; после backend/client boundary — полный suite.
- Временные import shims помечаются сроком удаления и не принимают новый код.

## Риски и меры

- **История Git:** использовать `git mv`, не форматировать все файлы вместе с
  переносом.
- **Alembic:** сохранить revision IDs и `down_revision`; меняется location, а не
  история миграций.
- **Docker/Compose:** сначала поддержать новый entrypoint при прежних service/env
  contracts, затем убрать старый.
- **Redis:** старые сообщения могут содержать старый Python module path;
  временно поддержать совместимый actor name/payload и дренировать очередь.
- **Windows upgrade:** не менять service name, install dir, config/credential
  paths и DPAPI scope в архитектурном commit.
- **Python pickle/import paths:** task payload остаётся JSON primitives; не
  сериализовать классы между версиями.
- **Frontend:** не менять UI/UX одновременно с переносом adapters/hooks.
- **Большой diff:** переносить по одному слою, не создавать параллельно старую и
  новую бизнес-реализацию.
- **Планы 41/42:** reliability behavior имеет собственные тесты/commits и
  переносится в новые paths без функциональных изменений.

## Запреты

- Не выполнять массовый перенос одним commit.
- Не менять API/DB/Redis/agent protocol только ради структуры каталогов.
- Не делать общий `shared` package между backend/frontend/winclient.
- Не импортировать infrastructure из domain/application/presentation.
- Не переносить use case или policy в router, ORM repository, React page либо
  Windows Host.
- Не удалять legacy client до подтверждённого native upgrade path.
- Не включать TrueNAS apply/cleanup во время архитектурного переноса.

## Статус

Целевая архитектура и последовательность перехода зафиксированы. Реализация не
начата; первым остаётся safety slice 41.1.
