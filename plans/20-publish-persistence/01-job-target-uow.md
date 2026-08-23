# 20. Publish job/target persistence и Dramatiq composition handler

## Цель

Зафиксировать в PostgreSQL-ориентированной persistence-модели draft publish
job и материализованный набор target-станций. Dramatiq handler должен получать
только идентификаторы, открывать свежий UoW на сообщение и заново загружать
доверенное состояние job/targets перед следующим application-срезом.

## Входы и зависимости

- планы 02, 03, 08, 11 и 19;
- `PublishJob` и state machine из `domain.publish`;
- `UnitOfWork`/`Protocol` boundary из `application.ports`;
- внутренний stable `station_id` и persistence identity `stations.id`;
- payload `job_id`, `correlation_id`, `idempotency_key` из `worker.tasks`.

## Scope этого подшага

### Модели и repository

Добавляются только две новые ORM-модели:

- `publish_jobs` с уникальным idempotency key, correlation ID, режимами
  `dry_run`/`allow_hot_switch`, state/step, confirmation и lifecycle timestamps;
- `publish_targets` с FK на job и station, уникальностью `(job_id, station_id)`,
  snapshot/result JSON, old/new mapping, switch/verify outcome, ошибкой и
  progress.

Application получает `PublishJobRepository` и `PublishTargetRepository` через
`Protocol`; concrete SQLAlchemy repositories переводят внутренний FK станции в
стабильный `station_id` домена. Создание job и targets выполняется одной UoW
транзакцией.

### Worker composition

Добавляется application-facing handler, который:

1. создаёт свежий UoW для каждого сообщения;
2. загружает job и targets по IDs;
3. сверяет `idempotency_key` и `correlation_id` с сохранённым job;
4. передаёт загруженное состояние следующему application executor через
   `Protocol`.

В этом подшаге executor может быть test spy/placeholder; переходы workflow и
изменение storage остаются отдельным следующим срезом. Долгая TrueNAS-операция
не удерживает persistence transaction.

## API routes

HTTP publish routes в этом подшаге не добавляются. Создание draft через API и
постановка сообщения в Redis будут отдельным application/presentation шагом
после проверки persistence composition.

## Migration plan

- Declarative metadata расширяется моделями job/target.
- Alembic revision не генерируется и не применяется автоматически.
- SQLite используется только для isolated repository tests.
- PostgreSQL/Redis/NAS runtime не подключаются.

## Ключевые тесты

- round-trip job и targets через SQLAlchemy repository;
- создание targets с stable station IDs при внутреннем FK;
- duplicate idempotency key отклоняется unique constraint;
- duplicate `(job_id, station_id)` отклоняется unique constraint;
- ошибка внутри UoW откатывает job и targets вместе;
- handler создаёт fresh UoW/исполнитель на каждое сообщение;
- handler отвергает неизвестный job и mismatched idempotency/correlation;
- task payload не содержит секретов, mapping или полного состояния.

Тесты простых column accessors, каждого SQLAlchemy mapping и Dramatiq broker
transport не добавляются.

## Запреты

- не создавать и не применять Alembic revision;
- не открывать соединение с реальным Redis broker;
- не подключать настоящий TrueNAS adapter;
- не добавлять `switch`, `destroy`, cleanup или удаление storage-объектов;
- не хранить общий session/UoW в actor или handler;
- не помещать пароль Basic Auth, TrueNAS API key или mapping payload в task.

## Критерий завершения

Модели и repositories проходят SQLite round-trip/constraint/rollback tests,
composition handler доказывает повторную загрузку состояния и fresh UoW,
`ruff check`, `ruff format --check` и общий pytest проходят. `STATE.md` и карта
планов отражают следующий шаг: application use case создания job и постановка
сообщения в Redis без запуска реального worker/NAS.

## Статус

- [x] scope, модели, transaction boundary и запреты зафиксированы;
- [x] ORM models и repository созданы;
- [x] Dramatiq composition handler создан;
- [x] ключевые tests созданы;
- [x] Ruff и pytest пройдены;
- [x] `STATE.md` обновлён.

Подшаг завершён. Следующий шаг — application use case для создания draft с
повторной проверкой station IDs и отдельный queue port для постановки
минимального Dramatiq payload. Redis broker и worker runtime остаются
выключенными.
