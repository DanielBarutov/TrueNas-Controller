# 30. TrueNAS LAN integration gate

## Цель

Проверить конкретную версию TrueNAS и локальный `/api/docs/` перед любым
runtime-подключением. Этот план не разрешает write-операции и не включает
реальный NAS автоматически.

## Входы

- завершённый план 29 с read-only transport/registry/fixtures;
- фактический адрес и версия NAS, предоставленные оператором;
- доступ к локальному `/api/docs/` или выгруженной официальной OpenAPI/JSON-RPC
  схеме конкретного экземпляра.

## Разрешённый scope

- сверить API family/patch version и методы с registry;
- при явном согласовании выполнить только `core.ping` и read-only query;
- подключить реальную WebSocket connection factory в composition root без
  переноса API key в application/domain/presentation;
- добавить integration tests, которые запускаются только при opt-in env flag.

## Реализованный opt-in boundary

- `TrueNASRuntimeConfig` принимает только полный `ws://`/`wss://` URL,
  `TRUENAS_VERSION` и `TRUENAS_API_KEY` из внешней среды;
- `auth.login_with_api_key` выполняется через adapter boundary и не попадает в
  application DTO, логи или ошибки;
- `websockets` connection factory отключает неявный proxy и переводит
  library-specific close errors в transport reconnect errors;
- `tests/truenas_adapter/test_integration.py` пропускается по умолчанию и
  запускается только с `RUN_TRUENAS_SMOKE=1`.

## Запрещено до отдельного согласования

- snapshot create/clone/destroy/delete;
- `iscsi.targetextent.update`, mapping switch и cleanup;
- запуск через production Redis или публикация на реальные станции;
- запись API key в git, fixtures, логи, UI, agent payload или exception text;
- обход несовпадения локальной схемы простым расширением allow-list.

## Чекап готовности

- [x] оператор сообщил фактическую версию NAS: `25.10.5`;
- [x] live `/api/docs/current/` конкретного NAS отдал документацию `TrueNAS API v25.10.5 (current)`; endpoint не сохранён в репозитории;
- [x] registry подтверждён для этой API family и read-only methods;
- [x] opt-in runtime config, API-key auth boundary и skipped-by-default smoke test созданы;
- [ ] отдельное явное согласование на LAN read-only smoke check получено;
- [ ] integration run выполнен с redacted output;
- [ ] результат и расхождения занесены в `STATE.md`.

## Следующий шаг

До отдельного согласования smoke check остаёмся на fixtures и contract tests
из плана 29. Временный внешний доступ к docs следует закрыть после проверки.
