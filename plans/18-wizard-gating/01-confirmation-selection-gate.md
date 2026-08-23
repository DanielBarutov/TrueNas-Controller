# 18. Preflight wizard gating

## Цель

Зафиксировать application/domain gate между preflight и будущим publish job:
admin check, явное подтверждение оператора и независимый результат каждой
выбранной станции.

## Изменяемые модели

- `WizardGateStatus`: `ready` или `blocked`;
- `WizardGateInput`: admin report, client reports, selected station IDs,
  confirmation (`True`/`False`/`None`);
- `WizardGateResult`: status, safe reasons и selected IDs.

## API routes

В этом подшаге routes не добавляются. Gate вызывается будущим publish application
service; browser не может самостоятельно снять blocking state.

## Migration plan

Миграции не создаются. Confirmation/audit/job persistence появятся вместе с
publish job plan.

## Ключевые тесты

- admin block/unknown блокирует переход;
- отсутствие или отрицательное подтверждение блокирует переход;
- пустой selection блокирует переход;
- missing client report блокирует переход;
- block/unknown выбранного client блокирует переход;
- pass/warning всех выбранных clients и confirmation=True дают ready.

## Запреты

- не создавать publish job;
- не диспатчить Dramatiq task;
- не выполнять TrueNAS/mock storage operations;
- не считать warning/unknown одинаковыми;
- не принимать station IDs как доказательство preflight без server-side reports.

## Критерий завершения

Wizard gate чистый, детерминированный и покрывает safety invariants; следующий
этап может начать draft publish job и Dramatiq fake workflow.

## Статус

- [x] wizard gate models созданы;
- [x] gate evaluator создан;
- [x] ключевые gate tests созданы;
- [x] проверки и `STATE.md` обновлены.

Подшаг завершён. Gate не создаёт job и не вызывает worker; следующий этап —
draft publish job и deterministic fake workflow на Dramatiq/Redis boundary.
