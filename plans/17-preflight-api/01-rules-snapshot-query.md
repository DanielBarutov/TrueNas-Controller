# 17. Process rules persistence и preflight API

## Цель

Подключить чистый preflight evaluator к актуальным station/rules/snapshot данным
через UoW и открыть операторский read-only endpoint `POST /api/v1/preflight`.

## Изменяемые модели

- `process_rules`: name, role, required_closed, severity, enabled,
  persistent_policy и timestamps;
- latest `process_snapshots` query поверх уже сохранённых heartbeat records;
- preflight response: aggregate status и explainable checks.

## API routes

- `POST /api/v1/preflight` — Basic Auth, station ID и read-only policy параметры;
- response содержит `pass/block/unknown/warning`, `can_publish`, check code/message
  и observed timestamp;
- publish/switch/cleanup routes не добавляются.

## Migration plan

1. Добавить `process_rules` в `Base.metadata`.
2. Проверить SQLite metadata/tests.
3. Alembic revision только подготовить к отдельной генерации после review;
   автоматически не генерировать и не применять.

## Ключевые тесты

- rules repository фильтрует enabled и role-specific rules;
- latest snapshot query отдаёт последнюю запись;
- application preflight возвращает block для активного required-closed процесса;
- отсутствие snapshot возвращает unknown;
- unknown не даёт `can_publish=True`;
- API требует Basic Auth и преобразует report в стабильный response.

## Запреты

- не менять NAS и не запускать publish worker;
- не принимать snapshot из browser;
- не считать старый snapshot актуальным;
- не писать preflight result как audit/job state до отдельного workflow-плана.

## Статус

- [x] process rule model/repository созданы;
- [x] latest snapshot port/query созданы;
- [x] application preflight query создан;
- [x] `POST /api/v1/preflight` создан;
- [x] ключевые tests созданы;
- [x] проверки и `STATE.md` обновлены.

Подшаг завершён. `unknown` и blocking остаются запрещающими publish, а
preflight result пока не записывается в job/audit state. Следующий шаг — wizard
gating/human confirmation.
