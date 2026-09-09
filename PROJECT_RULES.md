# Правила разработки проекта

Этот документ описывает обязательные правила для Python-приложения. Текущий статус выполнения планов находится в [STATE.md](/home/daniel/tnas/STATE.md), а исходные ограничения проекта — в [CODEX.md](/home/daniel/tnas/CODEX.md).

## Архитектурная модель

Основные слои backend:

```text
presentation ──────→ application ──────→ domain
                           ↑                 ↑
                           └── infrastructure┘
```

`backend/src/tnas_controller/bootstrap/{api,worker}.py` — composition roots: они
собирают зависимости, создают приложение/worker и подключают concrete adapters.
Бизнес-логика в bootstrap запрещена.

### `presentation`

- FastAPI routers, HTTP/WebSocket handlers, auth boundary, DTO и схемы входа/выхода;
- преобразует transport data в команду application слоя;
- вызывает use case и отображает результат;
- не содержит SQL, SQLAlchemy queries, TrueNAS method names и бизнес-ветвления;
- не выполняет долгие storage-операции внутри HTTP handler.

### `application`

- use cases, application services, workflow orchestration, policies;
- управляет транзакционной границей через UoW;
- зависит только от domain и `Protocol`-портов;
- повторно проверяет входные IDs и preconditions;
- не знает конкретные SQLAlchemy session, Redis client или WebSocket transport.

### `domain`

- entities, value objects, enums, domain rules и state transitions;
- чистый Python без FastAPI, SQLAlchemy, Dramatiq, Redis, psutil и TrueNAS SDK;
- не выполняет IO и не знает о способе хранения;
- содержит только правила, которые должны быть истинны независимо от инфраструктуры.

### `infrastructure`

- SQLAlchemy models/repositories, Alembic, Redis/Dramatiq, TrueNAS JSON-RPC,
  config, security и observability adapters;
- реализует порты application слоя;
- отвечает за persistence и transaction mechanics;
- не принимает бизнес-решение, можно ли переключать станцию;
- может импортировать application/domain, но не импортируется ими.

### Внешние адаптеры

Worker и TrueNAS являются backend infrastructure adapters. Windows-agent —
отдельный продукт `winclient`, а не backend adapter:

- Dramatiq task только принимает сообщение, создаёт свежий UoW и вызывает application use case;
- TrueNAS adapter реализует Protocol и скрывает JSON-RPC/WebSocket;
- агент не получает TrueNAS secret и не содержит бизнес-решения публикации.

## Зависимости

Разрешённое направление:

```text
presentation → application → domain
infrastructure ────────────→ application/domain ports
bootstrap ────────────────→ presentation/application/infrastructure/domain
```

Запрещено:

- `presentation → infrastructure` в обход application;
- `domain → SQLAlchemy/FastAPI/Dramatiq/Redis`;
- `application → concrete adapter`;
- глобальная общая SQLAlchemy session или UoW между запросами/сообщениями;
- вызов TrueNAS напрямую из browser, frontend или agent.

Backend, frontend и winclient не импортируют source packages друг друга. Их
совместимость проверяется через versioned HTTP/JSON contracts и fixtures.

## SOLID и ООП

- Один класс — одна причина для изменения.
- Use case должен иметь одну понятную ответственность и явные зависимости.
- Интерфейсы маленькие и предметные; не создавать универсальные `Manager`/`Service` без конкретной ответственности.
- Зависимости передаются через конструктор или фабрику composition root.
- Высокоуровневая application-логика зависит от абстракции порта, а не от реализации.
- Не использовать наследование для повторного использования кода, если достаточно композиции.
- Не скрывать побочные эффекты в properties и magic methods.

## Порты и `Protocol`

Для портов использовать `typing.Protocol`, а не `abc.ABC` и не наследование от абстрактных базовых классов.

Примеры портов:

- `UnitOfWork` и фабрика UoW;
- `StationRepository`, `PublishJobRepository`;
- `TrueNASClient`;
- `AgentGateway`;
- publisher progress/events.

Порт принадлежит внутреннему слою, который формулирует потребность. Concrete implementation находится во внешнем слое. Runtime-checkable Protocol использовать только если реально нужна runtime-проверка.

## Unit of Work

- Один HTTP use case или одна Dramatiq task получает свежий UoW.
- UoW открывает transaction boundary и владеет repository instances.
- Успех завершается одним `commit`; исключение приводит к `rollback`.
- Не передавать UoW между concurrent tasks и не хранить его в глобальном состоянии.
- После commit/rollback UoW закрывается.
- Длинные TrueNAS операции не должны удерживать БД-транзакцию дольше необходимого; состояние стадии фиксируется отдельными короткими транзакциями.
- Аудит перехода состояния и изменение состояния должны commit-иться атомарно.

## Worker

- Использовать **Dramatiq** с Redis broker.
- Task payload содержит IDs и idempotency/correlation data, а не доверенное состояние целиком.
- Task повторно загружает состояние из БД и применяет preconditions.
- На каждое сообщение создаётся новый UoW и application use case.
- Retry допускается только для идемпотентных стадий и с обработкой unknown outcome.

## Тестирование

Тестируем только ключевую логику, без избыточного покрытия очевидного glue-кода.

Обязательные тесты:

- domain state transitions и критичные invariants;
- application workflow: preflight, idempotency, partial failure, rollback;
- UoW transaction boundary и критичные repository constraints;
- Protocol contract для TrueNAS mock и agent gateway;
- security checks для auth, redaction и отсутствия destructive operations.

Не писать отдельные тесты на каждую простую DTO-модель, getter/setter, очевидный passthrough и фреймворковую регистрацию маршрута, если там нет собственной логики. Интеграционные тесты с реальным NAS — отдельный профиль и только после согласования.

## Ruff и форматирование

До архитектурного переноса единая конфигурация хранится в корневом
`pyproject.toml`; после плана 42 backend и legacy Python client получают
собственные manifests, а общие Ruff правила синхронизируются без смешивания
runtime dependencies.

- Python target: 3.12;
- форматирование выполняется Ruff formatter;
- импортами управляет Ruff isort (`I`);
- порядок: standard library → third-party → first-party → local relative;
- first-party пакеты проекта перечисляются в `known-first-party`;
- ручные исключения для сортировки импортов не добавлять без причины;
- перед завершением изменения запускать `ruff check` и `ruff format --check` на затронутых Python-файлах.

## Рабочий цикл

1. Прочитать `CODEX.md`, `STATE.md`, `PROJECT_RULES.md` и активный план.
2. Перед изменением определить слой, use case, модель и ключевые тесты.
3. Сначала обновить план, если решение меняет архитектуру или контракт.
4. Реализовать минимальное изменение в правильном слое.
5. Проверить ключевую логику, Ruff и отсутствие секретов.
6. Обновить `STATE.md`: статус, чекап, открытые вопросы и следующий шаг.

## Запреты

- Не писать секреты в README, планы, git, frontend bundle и логи.
- Не добавлять `ABC` для портов.
- Не переносить SQL в presentation.
- Не добавлять тесты ради процента покрытия.
- Не выполнять реальные TrueNAS write/destroy операции вне утверждённого этапа.
