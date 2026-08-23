# 29. Versioned TrueNAS read-only adapter contract

## Цель

Зафиксировать application Protocol и deterministic fixtures для read-only
TrueNAS JSON-RPC 2.0 over WebSocket adapter, не подключаясь к реальному NAS.
Методы и параметры сверяются с официальными документами и настраиваемой
версией API.

## Scope

- transport Protocol: request ID, timeout, reconnect и redacted errors;
- versioned method registry только для discovery/read operations, необходимых
  для target/extent/zvol/snapshot metadata;
- read-only adapter DTO/mapper в `truenas_adapter`;
- fixtures и contract tests на mock transport;
- TrueNAS API key остаётся backend/worker secret и не входит в domain/task/UI.

## Ключевые тесты

- request/response correlation и timeout mapping;
- version registry rejects unsupported method/version;
- fixture mapping returns safe domain/application data;
- malformed/unknown JSON-RPC error does not become success;
- no method name performs switch, destroy or cleanup.

## Migration/runtime plan

Модели и Alembic не меняются. Реальный `/api/docs/`, LAN NAS, WebSocket
connection и API key не используются; сначала проверяются только публичные
официальные docs и локальные fixtures.

## Статус

- [x] scope и integration gate зафиксированы;
- [ ] transport/method Protocol созданы;
- [ ] read-only adapter и fixtures созданы;
- [ ] ключевые contract tests созданы;
- [ ] `STATE.md` обновлён.
