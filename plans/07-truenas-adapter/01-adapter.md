# 07. TrueNAS adapter

## Цель

Изолировать versioned JSON-RPC 2.0 over WebSocket API TrueNAS и сначала доказать workflow на deterministic fake.

Проверенная документальная база: API v25.10.5, JSON-RPC transport, `core.ping`, `pool.dataset.query`, `pool.snapshot.query`, `pool.snapshot.create`, `pool.snapshot.clone`, `iscsi.target.query`, `iscsi.extent.query`, `iscsi.targetextent.query` и `iscsi.extent.update`. Полный список ссылок и границы документальной проверки находятся в [`docs/ONLINE_DOCS.md`](../../docs/ONLINE_DOCS.md).

## Обязательный порядок

1. Открыть официальные документы TrueNAS SCALE 25.10 из `CODEX.md`.
2. Зафиксировать проверенную дату/версию и ссылки в `docs/ONLINE_DOCS.md`.
3. Для каждого нужного метода сохранить имя, параметры, response shape, error shape и источник.
4. Реализовать transport и mock по документированному контракту.
5. Прогнать read-only mock/integration contract tests.
6. Только после отдельного согласования подключить реальный NAS в LAN.
7. На реальном NAS сначала выполнять только read-only calls.
8. Mapping switch включать только после mock acceptance и теста одной выделенной станции.

## Модули

### `websocket_jsonrpc.py`

Transport: connection lifecycle, authentication, request ID, timeout, reconnect, response correlation, bounded retry, safe logging. Не логировать key и raw auth frame.

### `method_registry.py`

`TRUENAS_VERSION` → method names/params/normalizers. Версия не должна быть свободной строкой из browser. Unknown version — fail closed для write operations.

Для v25.10 `iscsi.extent.update` используется только для замены `device/file`
существующего extent. `iscsi.targetextent.update` в workflow не используется:
association target → extent и LUN сохраняются.

### Typed adapter port

Операции высокого уровня:

- read zvol/dataset/snapshot/clone;
- read target/extent/association;
- create snapshot;
- create writable clone;
- update device/file существующего extent — отдельный capability, за feature gate;
- read-back mapping;
- cleanup — не включать в обычный adapter surface до отдельного плана.

Каждая write operation принимает trusted internal object refs, а не пользовательские path/IDs без валидации.

### `mock_client.py`

In-memory deterministic model: master, snapshots, clones, target→extent mapping, injected failures, delays, idempotency behavior and read-back. Mock должен моделировать partial failure и unknown outcome после timeout.

### `fixtures/`

JSON responses по документированным схемам, включая success/error/unknown fields. Fixture name содержит version и method category. Не выдавать fixture за подтверждение работы с реальным NAS.

## Safety policy

- Allowlist методов и аргументов.
- Label/station ID — safe slug с ограниченной длиной и символами.
- Перед clone/switch проверять ownership и station mapping.
- Один station — один writable clone/LUN.
- Перед switch читать old mapping и сравнивать с ожидаемым.
- После switch делать read-back.
- При timeout не повторять blindly: сначала read-back.
- `allow_hot_switch` false по умолчанию.
- `destroy` отсутствует в MVP adapter/write path.

## Capability model

Adapter сообщает capabilities: `read_only`, `snapshot`, `clone`, `mapping_switch`, `hot_switch`. Workflow выбирает поведение по capability и policy; отсутствие capability не обходится прямым websocket вызовом.

## Интеграционный gate

Для реального NAS нужны отдельные environment flag, явное подтверждение, LAN-only endpoint, secret injection и выделенная тестовая станция. Интеграционные тесты не запускаются в обычном `pytest`; отдельный opt-in profile и safety precheck должны явно подтвердить цель.

## Проверяемые результаты

Структурная проверка — файлы/типизация/fixture schema. Runtime mock — операции в fake state. Интеграционная проверка — фактические response/mapping на согласованном NAS. Эти уровни не смешивать в отчёте.
