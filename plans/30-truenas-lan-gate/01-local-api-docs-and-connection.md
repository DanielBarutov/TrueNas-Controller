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

## Запрещено до отдельного согласования

- snapshot create/clone/destroy/delete;
- `iscsi.targetextent.update`, mapping switch и cleanup;
- запуск через production Redis или публикация на реальные станции;
- запись API key в git, fixtures, логи, UI, agent payload или exception text;
- обход несовпадения локальной схемы простым расширением allow-list.

## Чекап готовности

- [ ] оператор сообщил фактическую версию NAS;
- [ ] локальный `/api/docs/` или эквивалентная схема сохранена вне секретов;
- [ ] registry подтверждён для этой API family;
- [ ] отдельное явное согласование на LAN read-only smoke check получено;
- [ ] integration run выполнен с redacted output;
- [ ] результат и расхождения занесены в `STATE.md`.

## Следующий шаг

До получения входов остаёмся на fixtures и contract tests из плана 29.
