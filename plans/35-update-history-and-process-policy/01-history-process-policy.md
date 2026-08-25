# План 35 — история обновлений и политика процессов

## Цель

Добавить оператору историю publish-заданий и web-настройку списка процессов,
которые агент обязан показать закрытыми перед обновлением. Повторная проверка
должна повторно читать свежий heartbeat/process snapshot и не обходить серверный
gate.

## Входы

- существующие `publish_jobs`/`publish_targets` и read model;
- `ProcessRule`/preflight evaluator и snapshots агентов;
- Basic Auth собственного API и React operator console.

## Выходы

- `GET /api/v1/publish/jobs` с безопасной историей;
- `GET/POST/DELETE /api/v1/process-rules` для операторской политики;
- кнопка «Повторить проверку» в publish wizard;
- отдельный экран политики процессов с пояснениями полей;
- ключевые application/repository/presentation/frontend тесты.

## Инварианты и запреты

- список процессов не зашивается в код и не считается доказательством, если
  snapshot устарел;
- `required_closed=true` + `blocking` блокирует dispatch до закрытия процесса;
- повторная проверка вызывает только собственный API и не меняет TrueNAS;
- история не раскрывает API key, raw mapping или credential;
- удаление правила не удаляет process snapshots и publish history.

## Чекап

- [x] application/repository/API реализованы;
- [x] UI и retry реализованы;
- [x] миграция не требуется: таблица `process_rules` уже существует;
- [x] Python/frontend tests, Ruff и build пройдены;
- [ ] пользовательский Compose runtime проверит миграции и новый UI отдельно.
