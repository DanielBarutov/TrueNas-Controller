# 27. Fake worker executor и persisted workflow results

## Цель

Соединить уже проверенный `FakePublishWorkflow` с persisted job/target rows и
Dramatiq handler через application `PublishTaskExecutor` Protocol. Worker
должен повторно загрузить state, выполнить только deterministic fake adapter и
сохранить per-target results без real Redis/NAS.

## Scope

- executor получает job/targets после свежей загрузки handler;
- fake adapter/workflow остаётся единственным storage implementation;
- dry-run не мутирует fake mappings;
- job status и target preflight/switch/verify/error/progress сохраняются через
  короткие UoW transactions;
- повторная доставка одного outbox event остаётся идемпотентной;
- неизвестный fake outcome сохраняется как recovery-required, старый mapping
  не удаляется.

## Ключевые тесты

- persisted dry-run result сохраняет simulation statuses;
- successful fake apply сохраняет completed/verified states;
- partial failure сохраняет успешный target и ошибку только failed target;
- duplicate executor delivery не создаёт второй master/clone;
- handler/executor не принимает полный state из task payload;
- real Redis/NAS/storage destroy не вызываются.

## Запреты

Не подключать настоящий TrueNAS, не добавлять mapping switch/destroy в real
adapter, не запускать production Redis и не считать fake acceptance
integration proof.

## Статус

- [x] scope зафиксирован;
- [x] executor и persistence mapper созданы;
- [x] ключевые tests созданы;
- [x] `STATE.md` обновлён.

Подшаг завершён. Fake executor повторно загружает persistence state через
handler, не держит UoW во время fake storage workflow и сохраняет verified/
partial/simulated outcomes. Следующий шаг — end-to-end acceptance одного
полного fake pipeline.
