# 22. Presentation contract для создания publish draft

## Цель

Подключить первый publish endpoint собственного API: operator с Basic Auth
создаёт draft через application use case и получает безопасное summary job с
материализованными station IDs. HTTP-слой не знает SQLAlchemy, Dramatiq или
TrueNAS и не запускает worker автоматически.

## Входы и зависимости

- API contract из плана 05 и Basic Auth boundary;
- `CreatePublishJobUseCase` из плана 21;
- `PublishJobDraft`, `PublishJob`, `PublishTarget` из domain/application;
- composition root `main.py`.

## Scope

### Presentation

Добавляются Pydantic request/response schemas и route:

```text
POST /api/v1/publish/jobs
```

Request содержит label, game, optional description, dynamic station IDs,
idempotency key, optional correlation ID, а также безопасные defaults
`dry_run=true` и `allow_hot_switch=false`. Route вызывает только application
use case, переводит validation в 422, повторный key с другим request shape в
409 и требует Basic Auth.

Response не возвращает secrets, mappings, credentials или полный persistence
record; содержит job ID, correlation/idempotency metadata, state, режим и
выбранные stable station IDs.

### Composition

`main.py` передаёт concrete draft use case в `create_app`. Вызов enqueue/Redis
остаётся отдельной командой и не является побочным эффектом POST draft.

## Migration plan

Миграции не меняются; endpoint использует таблицы из планов 20–21. Revision не
генерируется и не применяется.

## Ключевые тесты

- valid Basic Auth reaches application use case and returns 201 summary;
- missing/wrong Basic Auth returns 401 before use case;
- application validation maps to 422;
- idempotency conflict maps to 409;
- response contains stable station IDs and no secret/mapping fields.

Не тестировать FastAPI registration и Pydantic passthrough отдельно без
собственной логики.

## Запреты

- не enqueue-ить Dramatiq message из этого route;
- не подключать Redis broker или TrueNAS;
- не класть пароль Basic Auth, API key или mappings в
  response/logs/repository;
- не переносить station selection validation из application в presentation.

## Критерий завершения

Route подключён через composition root, auth/error mapping и response shape
проверены ключевыми API tests, Ruff/pytest проходят. Следующий шаг — GET job
read model и отдельная operator confirmation/preflight command; storage write
и реальный worker/NAS остаются выключенными.

## Статус

- [x] scope и HTTP safety boundary зафиксированы;
- [x] request/response schemas созданы;
- [x] route и composition root подключены;
- [x] ключевые API tests созданы;
- [x] Ruff и pytest пройдены;
- [x] `STATE.md` обновлён.

Подшаг завершён. Следующий шаг — GET job read model с per-target status и
progress, без выдачи storage mappings или секретов.
