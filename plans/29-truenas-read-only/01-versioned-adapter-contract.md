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

## Реализовано

- application DTO и Protocol для read-only metadata без storage write-портов;
- JSON-RPC 2.0 transport с correlation по request ID, timeout mapping,
  reconnect budget и redacted remote errors;
- registry для API family `25.10`, разрешающий только `core.ping` и query
  methods для dataset/snapshot/iSCSI metadata;
- fixture `truenas_adapter/fixtures/25.10/read_only.json` без секретов и
  зависимости от реального NAS;
- adapter mapper с отказом на malformed shape и false ping.

## Проверки

- `uv run ruff check .` — passed;
- `uv run ruff format --check .` — passed;
- `uv run pytest -q` — `93 passed`;
- real WebSocket, Redis broker, API key и storage write не запускались.

## Статус

- [x] scope и integration gate зафиксированы;
- [x] transport/method Protocol созданы;
- [x] read-only adapter и fixtures созданы;
- [x] ключевые contract tests созданы;
- [x] `STATE.md` обновлён.
