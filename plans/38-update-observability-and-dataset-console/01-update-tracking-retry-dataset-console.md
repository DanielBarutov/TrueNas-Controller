# План 38. Статус обновления, JSON-RPC retry и консоль датасетов

## Цель

Показать оператору дату последнего успешно проверенного обновления для каждой
станции, сделать временные сбои TrueNAS JSON-RPC переживаемыми и добавить в
веб-консоль управляемый список созданных publish-версий с постановкой cleanup
в worker.

## Входы и зависимости

- текущая модель `Station` и `publish_artifacts`;
- worker Dramatiq/Redis и TrueNAS WebSocket adapter;
- HTTP Basic Auth и React/Vite operator console;
- отдельный cleanup apply gate из плана 37.

## Решения и инварианты

- `stations.last_update_at` записывается только после успешного
  non-dry-run результата `VERIFIED`; dry-run и ошибки дату не меняют;
- retry ограничен бюджетом попыток и bounded exponential backoff;
  повторяется тот же JSON-RPC request, но после reconnect API-key transport
  повторно авторизует новую WebSocket-сессию;
- protocol/remote JSON-RPC errors не считаются временными и не ретраятся;
- UI получает только tracked `publish_artifacts`, отправляет worker UUID,
  TrueNAS API key остаётся только в worker;
- текущий dataset помечен как используемый и не выбирается для удаления;
  окончательное решение об удалении остаётся за TrueNAS/cleanup apply gate;
- реальный NAS, Redis broker и production migration не запускаются в рамках
  локального плана.

## Изменения

- domain/ORM/repository/API: `last_update_at` и Alembic revision;
- transport/runtime: retry timeout, connection/EOF и повторная auth-сессия;
- application/worker/API: dataset inventory и ручная cleanup dispatch;
- frontend: колонка последнего обновления и пункт «Датасеты» с checkbox;
- tests: persistence, use cases, API, worker, transport/runtime и frontend.

## Проверки и результат

- [x] `uv run pytest -q` — `231 passed, 1 skipped`;
- [x] `uv run ruff check .` и `uv run ruff format --check .`;
- [x] `uv run python -m compileall -q ...`;
- [x] `npm run test` — `11 passed`;
- [x] `npm run build`;
- [x] Alembic `upgrade head` и `current` на отдельной временной SQLite-БД;
- [x] live TrueNAS, production PostgreSQL migration и cleanup apply не
  выполнялись.

## Статус

Завершён локальный implementation slice. Следующий gate — применить миграцию
в пользовательском Compose и отдельно проверить worker/UI на тестовой станции.
