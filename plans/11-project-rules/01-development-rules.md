# 11. Правила разработки и проектная обвязка

## Цель

Зафиксировать единый способ разработки Python-приложения до создания runtime-кода, чтобы слои, зависимости, тесты и форматирование не менялись ситуативно.

## Принятые решения

- Чистая архитектура с основными слоями: `presentation`, `application`, `repository`, `domain`.
- `main.py` — только composition root: сборка зависимостей и запуск.
- HTTP/WebSocket routes принадлежат `presentation`.
- Use cases и workflow принадлежат `application`.
- Чистые бизнес-правила принадлежат `domain`.
- Persistence и UoW implementation принадлежат `repository`.
- Порты описываются через `typing.Protocol`, `abc.ABC` не используется.
- Транзакционная граница — Unit of Work.
- Worker — Dramatiq, broker — Redis.
- Тестируются только ключевые domain/application/integration invariants.
- Ruff используется для lint, format и сортировки импортов.

## Контракт слоёв

| Слой | Может импортировать | Не должен импортировать |
|---|---|---|
| `domain` | stdlib, собственные domain-модули | FastAPI, SQLAlchemy, Dramatiq, Redis, psutil, TrueNAS |
| `application` | domain, собственные Protocol ports | concrete repository/adapter/client |
| `presentation` | application DTO/use cases, web framework | SQL, TrueNAS transport, worker internals |
| `repository` | application/domain ports, SQLAlchemy, Alembic | presentation и UI |
| `worker` | application use cases, Dramatiq wiring | бизнес-правила в task body |
| `truenas_adapter` | application Protocol, WebSocket client | frontend и browser code |

## UoW contract

Минимальный application Protocol должен выражать `commit`, `rollback`, `__aenter__`, `__aexit__` и доступ к нужным repository ports. Реализация в repository создаёт новую SQLAlchemy session на каждый use case/task.

Длинные storage actions разбиваются на стадии. Между стадиями UoW закрывается, а состояние job/target и audit сохраняются короткими транзакциями.

## Test policy

Минимальный обязательный набор:

1. unit-тесты domain transitions и критичных policies;
2. application tests для preflight, idempotency, partial failure и rollback;
3. несколько repository/UoW tests на commit/rollback/constraints;
4. contract tests для fake TrueNAS и agent Protocol;
5. один-два API smoke/contract tests на критичные endpoints.

Не создавать тесты для тривиального DTO mapping и passthrough-кода без логики. Визуальные frontend-тесты добавлять только для wizard gating, красных флагов и опасных подтверждений.

## Ruff baseline

Конфигурация должна жить в `/home/daniel/tnas/pyproject.toml` и включать:

- target Python 3.12;
- `E`, `F`, `W`, `I`, `B`, `UP`, `SIM`, `RUF`;
- Ruff formatter;
- isort-настройки `known-first-party`, `combine-as-imports`, `force-sort-within-sections`;
- first-party имена всех Python-слоёв;
- проверки `ruff check` и `ruff format --check` в рабочем чекапе.

## Чекап перед реализацией

- [x] Правила записаны в `PROJECT_RULES.md`.
- [x] Правила добавлены в основную инструкцию `CODEX.md`.
- [x] Ruff baseline добавлен в `pyproject.toml`.
- [x] Создан Python package layout.
- [x] Созданы application/domain Protocol ports.
- [x] Создан repository UoW и проверены transaction boundaries.
- [x] Созданы первые ключевые tests.
