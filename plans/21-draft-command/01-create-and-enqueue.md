# 21. Draft publish command и enqueue port

## Цель

Добавить application use case создания draft publish job: повторно проверить
выбранные станции, материализовать targets в одной транзакции и безопасно
повторить запрос по idempotency key. Зафиксировать отдельный queue port и
concrete Dramatiq adapter, который передаёт только IDs/correlation data.

## Входы и зависимости

- `PublishJob`/`PublishTarget` и state machine из domain;
- `StationRepository`, `PublishJobRepository`, `PublishTargetRepository` и UoW;
- `PublishTaskPayload`/actor boundary из плана 19;
- persistence models/repositories из плана 20.

## Scope

### Application

`CreatePublishJobUseCase` принимает label, game, idempotency key, correlation ID
и произвольный список stable station IDs. Он:

1. отклоняет пустой или повторяющийся выбор;
2. перечитывает станции из repository и отклоняет неизвестные,
   disabled/deleted станции;
3. создаёт draft с `dry_run=True` и `allow_hot_switch=False` по умолчанию;
4. создаёт target rows в той же транзакции;
5. при повторе того же idempotency key возвращает прежний job только если
   request shape совпадает, иначе возвращает conflict.

`EnqueuePublishJobUseCase` загружает job в короткой UoW-транзакции, сверяет
correlation/idempotency и вызывает `PublishTaskQueue`.

### Queue adapter

`PublishTaskQueue` — `Protocol` application-слоя с primitive UUID/string
аргументами. `DramatiqPublishTaskQueue` — тонкий adapter вокруг actor; он не
создаёт Redis connection в тестах и не передаёт job state, mapping или secrets.

## API routes

Presentation route для создания job в этом подшаге не добавляется. HTTP DTO,
Basic Auth operator context и отдельная команда запуска publish появятся после
проверки use case/queue boundary.

## Migration plan

Новых таблиц и Alembic revision нет; используются `publish_jobs` и
`publish_targets` из плана 20. Revision не генерируется и не применяется.

## Ключевые тесты

- dynamic station selection materializes all selected targets;
- unknown/disabled/deleted/duplicate station IDs are rejected;
- draft defaults preserve dry-run and disable hot switch;
- same idempotency request returns existing job without duplicate rows;
- reused idempotency key with another request is rejected;
- enqueue loads durable state and passes only minimal payload to queue;
- mismatched correlation/idempotency and missing job do not enqueue;
- Dramatiq adapter delegates primitive payload to a fake actor without broker.

## Запреты

- не создавать HTTP route без отдельного presentation check;
- не подключать реальный Redis broker;
- не выполнять worker workflow и TrueNAS calls;
- не добавлять mapping switch, cleanup, destroy или storage delete;
- не хранить общий UoW/session в use case или queue adapter.

## Критерий завершения

Application draft/enqueue use cases и queue adapter проходят ключевые unit/
repository tests, Ruff и полный pytest. `STATE.md` отражает, что следующий
шаг — presentation contract/HTTP route или отдельный операторский command gate;
Redis/NAS runtime не запускались.

## Статус

- [x] scope и idempotency/transaction invariants зафиксированы;
- [x] draft use case создан;
- [x] queue Protocol и Dramatiq adapter созданы;
- [x] ключевые tests созданы;
- [x] Ruff и pytest пройдены;
- [x] `STATE.md` обновлён.

Подшаг завершён. Следующий шаг — presentation contract для создания draft;
enqueue остаётся отдельной application-командой и не вызывается HTTP route
автоматически.
