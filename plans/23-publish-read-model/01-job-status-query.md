# 23. Publish job read model

## Цель

Дать оператору безопасный read-only endpoint для восстановления состояния
publish job и target outcomes после обновления страницы или повторной доставки
worker message. Read model строится через application query и не раскрывает
storage mappings, credentials или TrueNAS API details.

## Scope

- application `GetPublishJobUseCase` загружает job и targets одним свежим UoW;
- presentation добавляет `GET /api/v1/publish/jobs/{id}` с Basic Auth;
- response содержит job state/step-safe metadata и per-target preflight,
  switch/verify statuses, errors и progress;
- missing job maps to 404; no queue, storage write или worker side effect.

## Ключевые тесты

- query возвращает job и dynamic target list;
- unknown job даёт application not-found;
- API требует Basic Auth и возвращает safe target summary;
- raw mapping, credentials и API key не попадают в response;
- 404 error mapping проверен.

## Migration plan и запреты

Модели и миграции не меняются. Redis, Dramatiq broker, TrueNAS и любые
storage write/destroy операции не запускаются.

## Критерий завершения

Query и GET route проходят ключевые tests, Ruff и полный pytest. Следующий
шаг — отдельная operator confirmation/preflight command перед enqueue.

## Статус

- [x] scope и безопасный response boundary зафиксированы;
- [x] application query создан;
- [x] GET route создан;
- [x] ключевые tests созданы;
- [x] Ruff и pytest пройдены;
- [x] `STATE.md` обновлён.

Подшаг завершён. Следующий шаг — отдельная operator confirmation/preflight
command перед enqueue; GET остаётся read-only.
