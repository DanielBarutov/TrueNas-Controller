# 13. Persistence models и concrete UoW

## Цель

Реализовать первый infrastructure-подшаг read-only backend: SQLAlchemy-модели
`stations`/`agents`, repository для чтения станций и concrete UoW, который
создаёт новую `AsyncSession` на каждый use case или worker task.

## Scope

### Изменяемые модели

В `repository/models.py` создаются только две таблицы:

- `stations`: UUID identity, stable `station_id`, имя, hostname, роль,
  operational state, enabled/soft-delete flags, tags, mapping references и
  timestamps;
- `agents`: one-to-one station binding, agent metadata, hashed credential
  metadata, heartbeat/process/drive timestamps, address snapshots и status.

Domain остаётся независимым от SQLAlchemy. Persistence model преобразуется в
`domain.station.Station` внутри repository mapper.

### API routes

В этом подшаге HTTP routes не добавляются. Health и stations CRUD появятся после
проверки repository/UoW boundary.

### Migration plan

1. Declarative metadata фиксирует только `stations` и `agents`.
2. Следующим отдельным шагом создаётся Alembic revision для PostgreSQL.
3. Revision сначала генерируется/проверяется, но автоматически не применяется.
4. SQLite используется только в isolated repository tests; production target —
   PostgreSQL.

### Ключевые тесты

- repository добавляет и читает station через domain port;
- `include_disabled` управляет read-model фильтрацией;
- UoW commit сохраняет изменения;
- исключение внутри context manager вызывает rollback;
- duplicate stable `station_id` отклоняется constraint-ом;
- новая UoW-фабрика не переиспользует session между вызовами.

Тесты каждого SQLAlchemy column accessor и простого passthrough не добавляются.

## Реализационный порядок

1. Зафиксировать `DeclarativeBase` и naming convention.
2. Добавить typed models и связи/ограничения только для двух таблиц.
3. Добавить async session factory и concrete UoW.
4. Добавить SQLAlchemy station repository и domain mapping.
5. Запустить SQLite repository tests, Ruff и import boundary checks.

## Запреты

- не создавать и не применять Alembic revision в этом подшаге;
- не подключаться к реальному PostgreSQL/NAS;
- не добавлять storage write operations;
- не импортировать repository из domain/application;
- не использовать глобальную session или общий UoW;
- не хранить секреты и plaintext agent credentials.

## Критерий завершения

Две модели импортируются, repository/UoW проходят ключевые SQLite tests,
rollback и unique constraint доказаны runtime-проверкой, а миграционный шаг и
следующий API-подшаг записаны в `STATE.md`.

## Статус

- [x] models и metadata созданы;
- [x] async session/UoW созданы;
- [x] station repository создан;
- [x] ключевые repository/UoW tests созданы;
- [x] проверки выполнены;
- [x] `STATE.md` обновлён.

Подшаг persistence завершён. Следующее изменение должно отдельно зафиксировать
Alembic configuration/revision и read-only API; текущая revision не генерировалась
и не применялась.
