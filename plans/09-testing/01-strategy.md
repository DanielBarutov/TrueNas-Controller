# 09. Стратегия тестирования

## Цель

Доказывать отдельно структуру, runtime-поведение, безопасность workflow и интеграцию с конкретной версией TrueNAS.

Политика проекта — тестировать только ключевую логику и инварианты. Тривиальный DTO mapping, простую регистрацию маршрута и очевидный passthrough не тестировать отдельно без собственной логики.

## Пирамида

### Unit

- domain enums и допустимые переходы;
- freshness calculation;
- process rules/severity/persistent policy;
- label/station ID validation;
- idempotency key behavior;
- API schema/error mapping;
- agent payload normalization;
- adapter method registry и JSON-RPC correlation.

### Repository/integration

- миграции на PostgreSQL;
- SQLite compatibility profile, если он поддержан;
- uniqueness и foreign keys;
- transaction + audit atomicity;
- advisory lock/concurrency;
- snapshot retention rules.

### Application workflow

С Dramatiq test broker/worker, fake repositories и fake adapter проверить:

- admin/client preflight;
- stale/offline/blocking process/low space;
- human confirmation Да/Нет;
- multi-select произвольного размера;
- один master на job;
- clone только выбранных;
- partial failure;
- retry/idempotent replay;
- unknown outcome/read-back;
- rollback одной станции;
- cleanup остаётся dry-run.

### API

Contract tests для endpoints, auth, 400/401/403/404/409/422/503, websocket reconnect и повторного получения current state.

### Agent

Mock `psutil`, access denied/no such process, drive state, backoff, enrollment, command allowlist, version compatibility.

### Frontend

Component/page tests для:

- tri-state freshness badges;
- disabled checkbox для stale/offline;
- exact blocking process/PID;
- wizard gating;
- partial result and rollback button;
- dry-run/hot-switch/cleanup warnings;
- reconnect to events.

### Security tests

- secret not present in frontend build and agent package;
- logs redact credentials;
- token one-shot/TTL/revoke;
- agent station binding;
- no arbitrary command;
- no storage destroy endpoint in MVP;
- browser cannot reach TrueNAS config.

### TrueNAS

- mock tests — обязательны и запускаются всегда;
- fixture schema tests — обязательны;
- реальный read-only integration — отдельный marker/profile;
- real write/switch — только выделенная LAN station и explicit environment confirmation.

## Fault injection matrix

Проверить ошибки на каждой стадии: timeout, connection reset, malformed response, auth failure, duplicate response, worker crash after request, DB commit failure, agent disappears, stale snapshot, mapping mismatch. Для каждого случая определить expected state и отсутствие destructive cleanup.

## Definition of Done для кода

1. Есть тесты на happy path и отказ соответствующего слоя.
2. Тест подтверждает не только HTTP 200, но и состояние БД, audit и fake storage.
3. Повтор команды проверен.
4. Ошибки/unknown state проверены.
5. Логи и секреты проверены.
6. Документировано, был ли тест структурным, runtime, визуальным или интеграционным.

## Инструментальная база

Ruff и pytest-конфигурация фиксируются в корневом `pyproject.toml`. Для импортов используется Ruff isort с `known-first-party` для слоёв приложения. Минимальные проверки перед завершением изменения: `ruff check` и `ruff format --check` на затронутых Python-файлах.

## Команды будут зафиксированы позже

До создания runtime-кода выбрать и записать в README команды `uv run pytest`, frontend test/build, lint/typecheck, Compose health и отдельный integration profile. Не считать отсутствие этих команд на пустом checkout ошибкой реализации.
