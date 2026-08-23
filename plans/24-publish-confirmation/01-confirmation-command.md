# 24. Operator confirmation и publish preflight command

## Цель

Связать существующий чистый wizard gate с persisted publish job без запуска
storage workflow: сервер повторно проверяет admin/client reports, фиксирует
confirmation в job state и переводит job только по разрешённым переходам.

## Scope

- application command загружает job/targets и свежие preflight reports;
- `evaluate_wizard_gate` остаётся единственным domain safety evaluator;
- blocked/unknown не превращаются в pass;
- при ready сохраняются confirmation/status в одной короткой транзакции;
- при blocked job не enqueue-ится и не вызывает adapter;
- отдельный HTTP command/DTO появится после application tests.

## Ключевые тесты

- admin/client block, missing report и no confirmation сохраняют безопасное
  состояние;
- all selected reports pass + explicit confirmation дают ready;
- invalid job state отклоняется;
- job/confirmation update commit-ится атомарно;
- worker/NAS/Redis не вызываются.

## Запреты

Не создавать mapping, не выполнять switch/destroy/cleanup, не enqueue-ить
Dramatiq и не подключать Redis/NAS в этом подшаге.

## Статус

- [x] scope зафиксирован;
- [x] application command создан;
- [x] ключевые tests созданы;
- [x] `STATE.md` обновлён.

Подшаг завершён. Следующий шаг — отдельный dispatch gate: только
`awaiting_confirmation` с явным подтверждением и pass/warning targets может
перевести job в `publishing` и вызвать queue port.
