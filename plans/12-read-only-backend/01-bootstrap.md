# 12. Каркас read-only backend

## Цель

Перевести проект из стадии документации в первый безопасный этап реализации: создать минимальный Python-каркас, зафиксировать внутренние порты и подготовить границу для будущего read-only API. На этом плане нет подключения к TrueNAS и нет storage write-операций.

## Входы

- [Дорожная карта](../10-implementation-roadmap/01-roadmap.md).
- [Архитектура слоёв](../01-architecture/01-layers.md).
- [Правила разработки](../../PROJECT_RULES.md).
- [Схема данных](../02-database/01-schema.md).
- [Стратегия тестирования](../09-testing/01-strategy.md).

## Scope текущей итерации

### Изменяемые модели

На этом подшаге реализуются только минимальные domain-модели, необходимые для определения границ:

- `StationRole` — `admin` или `client`;
- `StationStatus` — `online`, `stale`, `offline`, `disabled`;
- `Station` — immutable identity и операционное состояние станции.

SQLAlchemy-модели, Alembic и persistence schema остаются следующим подшагом плана 02.

### API routes

В текущей итерации HTTP routes не добавляются. Сначала фиксируются application ports и UoW-контракт; health и stations CRUD появятся после подключения concrete composition root.

### Migration plan

Миграции не создаются. После утверждения domain-модели следующий подшаг создаст только `stations` и `agents` в PostgreSQL-ориентированной схеме; destructive migration и hard delete не входят в scope.

### Ключевые тесты

- domain: корректное создание станции и запрет невалидной роли/статуса;
- application: структурная проверка `UnitOfWork` и `StationRepository` как `Protocol`;
- dependency check: domain не импортирует инфраструктуру.

Тесты простых `__init__.py`, пустого composition root и очевидных аннотаций не добавляются.

## Реализационный порядок

1. Создать package layout для слоёв и внешних adapters.
2. Добавить domain-модель станции без IO и framework imports.
3. Добавить application ports через `typing.Protocol`.
4. Добавить placeholder composition root без бизнес-логики.
5. Проверить Ruff и импортные границы.

## Запреты

- не подключать реальный NAS;
- не реализовывать `destroy`, cleanup, mapping switch или любой storage write;
- не помещать SQL/SQLAlchemy в domain/application;
- не создавать общий глобальный UoW/session;
- не добавлять пароль Basic Auth в код или документацию.

## Критерий завершения

Каркас импортируется стандартным Python runtime, domain остаётся чистым, порты определены через `Protocol`, Ruff проходит, а `STATE.md` содержит фактические изменённые файлы и следующий шаг.

## Статус

- [x] package layout создан;
- [x] domain-модель создана;
- [x] application ports созданы;
- [x] composition root placeholder создан;
- [x] проверки выполнены;
- [x] `STATE.md` обновлён;

Подшаг bootstrap завершён. План остаётся активным до перехода к concrete
SQLAlchemy UoW и persistence-моделям следующего подшага.
