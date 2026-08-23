# 19. Draft publish job и Dramatiq fake workflow

## Цель

Начать publish stage на deterministic fake storage: создать явную job state
machine, идемпотентные master/clone/switch/verify операции и Dramatiq task
boundary. Redis используется как broker; PostgreSQL остаётся источником job
state в следующем persistence подшаге.

## Изменяемые модели

- `PublishJobStatus` и допустимые переходы;
- `PublishJob` с `dry_run=True`, `allow_hot_switch=False`, idempotency и
  correlation IDs;
- fake storage state: master, per-station clone, old/new mapping и verify state.

## API routes

В этом подшаге HTTP publish routes не добавляются. Worker принимает только IDs и
идемпотency/correlation payload, а application workflow загружает state через
будущий repository port.

## Migration plan

Миграции не создаются. `publish_jobs`/`publish_targets` persistence — отдельный
следующий подшаг после стабилизации domain workflow.

## Ключевые тесты

- legal/illegal job state transitions;
- dry-run не меняет fake mapping;
- один master на job и один clone на station;
- повтор master/clone/switch/verify идемпотентен;
- partial failure не меняет успешные targets и не удаляет старый mapping;
- timeout/unknown state требует read-back;
- Dramatiq message payload содержит IDs, idempotency и correlation, но не secret
  или полный доверенный state.

## Запреты

- не подключать настоящий NAS;
- не добавлять `destroy`, cleanup или реальные iSCSI mapping calls;
- не хранить global UoW/session в actor;
- не передавать API key, raw mapping или credentials в task payload;
- не считать fake acceptance доказательством TrueNAS integration.

## Критерий завершения

Fake workflow и Dramatiq boundary проходят ключевые tests, а документация
разделяет domain/runtime fake proof от будущей PostgreSQL/TrueNAS integration.

## Статус

- [x] project dependencies для Dramatiq/Redis зафиксированы;
- [x] publish domain state machine создана;
- [x] fake adapter/workflow создан;
- [x] Dramatiq actor boundary создан;
- [x] ключевые tests созданы;
- [x] проверки и `STATE.md` обновлены.

Подшаг завершён. Fake workflow доказан на Python 3.12/uv, но PostgreSQL job
persistence, Redis broker execution и настоящий TrueNAS adapter ещё не
подключались. Следующий шаг — `publish_jobs`/`publish_targets` persistence и
composition handler для Dramatiq.
