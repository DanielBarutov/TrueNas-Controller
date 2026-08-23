# 01. Архитектура и слои

## Цель

Разделить систему так, чтобы опасные storage-операции были изолированы от HTTP и UI, а workflow можно было полностью тестировать на fake TrueNAS.

## Логическая схема

```text
React/Vite UI
    │ REST + WebSocket events
    ▼
FastAPI presentation/API
    │ commands, queries, auth, DTO validation
    ▼
Application services / workflow
    │ transactions, policies, state transitions
    ├── repositories ── PostgreSQL
    ├── job dispatcher ── Redis ── worker
    ├── agent gateway ── HTTPS/WebSocket ── Windows agents
    └── TrueNAS port ── adapter ── JSON-RPC WebSocket ── TrueNAS
```

## Обязательная структура Python-приложения

```text
main.py                         # composition root: wiring и запуск
presentation/                   # FastAPI routes, DTO, auth, WebSocket
application/                    # use cases, policies, Protocol ports
domain/                         # entities, value objects, rules, state machine
repository/                     # SQLAlchemy repositories, UoW, migrations
worker/                         # Dramatiq delivery adapter
truenas_adapter/                # external adapter для TrueNAS Protocol
agent/                          # отдельный Windows-агент
```

Зависимости core направлены внутрь: `presentation → application → domain`. `repository`, `worker` и `truenas_adapter` реализуют порты внутренних слоёв. `main.py` единственный composition root и не содержит бизнес-правил.

Порты описываются через `typing.Protocol`. `abc.ABC` для границ слоёв не используется.

## Слои

### 1. Presentation

Состав: React pages, components, forms, tables, status badges, event subscription.

Ответственность:

- отобразить станции, свежесть, ошибки, процессы и прогресс;
- провести оператора через wizard;
- отправить только собственные API-команды;
- показывать обязательные предупреждения для dry-run, hot switch и cleanup;
- не принимать решение о допустимости операции самостоятельно.

Граница: frontend не знает TrueNAS URL, API key, внутренние credentials и не вызывает TrueNAS.

### 2. API / presentation backend

Состав: FastAPI routers, request/response schemas, dependency injection, authentication boundary, error mapping.

Ответственность:

- проверить форму запроса и права оператора;
- загрузить актуальное состояние из БД;
- вызвать application service;
- вернуть стабильный API-контракт;
- принять heartbeat агента и нормализовать snapshot;
- создать command/job, но не выполнять долгие операции в HTTP handler.

Граница: router не содержит SQL, JSON-RPC method names и бизнес-ветвление workflow.

### 3. Application / use cases

Состав: `agent_registry`, `process_preflight`, `publish_workflow`, `rollback`, `cleanup`, policies.

Ответственность:

- оркестрировать use case;
- повторно проверять все station IDs на сервере;
- транзакционно менять job/state;
- применять freshness, process, drive, mapping и concurrency policies;
- формировать команды worker и audit events;
- обеспечивать idempotency.

Граница: use case зависит от портов, а не от конкретного SQLAlchemy или websocket-клиента.

### 4. Domain model / policies

Состав: enums, value objects, state transition rules, validation of labels, preflight result types.

Ответственность:

- описать допустимые состояния и переходы;
- различать `offline`, `stale`, `online`, `blocked`, `ready`, `switching`, `verified`, `error`;
- не позволять применить switch к недопустимому target;
- вычислить blocking/non-blocking/unknown результат проверки.

Граница: domain не выполняет сеть, файловую систему, SQL или Windows API.

### 5. Persistence

Состав: SQLAlchemy models, repositories, Alembic migrations, transaction/unit-of-work, advisory lock.

Ответственность:

- хранить источник истины о станциях, версиях, jobs, targets и аудите;
- обеспечить уникальность station/agent/token/idempotency keys;
- не терять старый mapping до успешной verify новой версии;
- выдавать консистентные read-model для UI.

Граница: repository не содержит решений о том, можно ли закрывать процесс или переключать станцию.

### 6. Worker / durable execution

Состав: очередь, task handlers, retry policy, timeout, progress events, recovery loop.

Реализационный выбор: **Dramatiq** как durable worker; Redis — broker и транспорт служебных событий. Источник истины для job остаётся PostgreSQL.

Ответственность:

- выполнять долгие mock/TrueNAS операции;
- идемпотентно делать стадии snapshot → clone → switch → verify;
- ограничивать параллельность и использовать DB lock;
- публиковать progress и audit events;
- сохранять compensation state при сбое.

Граница: worker не принимает произвольный mapping из payload; он загружает job и повторно применяет policy.

### 7. Agent gateway и protocol

Состав: enrollment, heartbeat endpoint, snapshot schema, refresh command, reconnect handling.

Ответственность:

- выдать одноразовый enrollment token и agent credential;
- принять подписанный/аутентифицированный snapshot;
- обновить freshness и last error;
- отправить только разрешённую server-initiated команду refresh.

Граница: агент не получает TrueNAS secrets и не имеет endpoint для arbitrary command execution.

### 8. TrueNAS adapter

Состав: transport, auth, request IDs, method registry, typed operations, mock client, fixtures.

Ответственность:

- говорить с versioned JSON-RPC WebSocket API;
- выполнять allowlisted read/snapshot/clone/mapping operations;
- нормализовать ошибки и timeout;
- вести correlation ID;
- позволять workflow работать с deterministic fake.

Граница: adapter не решает, какие станции выбрал оператор, и не удаляет storage без отдельного разрешённого use case.

### 9. Operations / deployment

Состав: Compose, secrets, healthchecks, backup/restore, logs, `OPERATIONS.md`.

Ответственность:

- поднять frontend/API/worker/PostgreSQL/Redis;
- обнаруживать остановку контроллера;
- ограничить bind address LAN/localhost;
- описать восстановление БД, расхождение БД и NAS и ручную сверку.

## Правила зависимостей

Разрешённое направление: `presentation → application → ports/domain`, а infrastructure реализует ports. Нельзя: `frontend → TrueNAS`, `domain → SQLAlchemy`, `router → worker internals`, `agent → NAS`.

## Сквозной идентификатор операции

Все команды, worker tasks, adapter requests и audit events должны передавать `correlation_id`. Для повторяемости отдельно хранится `idempotency_key`; он не заменяет job ID.

## Готовность слоя

Слой считается описанным, когда определены его входы, выходы, ошибки, владелец состояния, тестовый double и запрет на пересечение ответственности. Реализация считается готовой только после тестов соответствующего уровня из плана 09.
