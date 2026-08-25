# Проверенные онлайн-документы TrueNAS

Последняя проверка: **2026-08-23**

## Зафиксированная версия

- Документация API: **TrueNAS API v25.10.5**.
- Документация продукта: ветка **TrueNAS SCALE 25.10**.
- Настройка в проекте: `TRUENAS_VERSION=25.10`.
- Версия конкретного NAS подтверждена оператором как `25.10.5`.
- Через временно опубликованный оператором docs endpoint выполнен только
  безаутентификационный HTTP GET: ответ перенаправил на `/api/docs/current/` и
  содержит `TrueNAS API v25.10.5 (current)`. Сам адрес endpoint в репозитории
  не сохраняется.
- WebSocket, API key, Redis и любые runtime/write-вызовы на пользовательском NAS
  не выполнялись.
- Default Compose worker использует fake executor. Режим `truenas` теперь
  существует, но требует отдельного `TRUENAS_APPLY_ENABLED=true` и не включается
  наличием одного только API key.

## Базовые документы

| Тема | Официальный документ | Что используем |
|---|---|---|
| API overview | [API Reference](https://www.truenas.com/docs/scale/api/) | подтверждает versioned JSON-RPC 2.0 over WebSocket с 25.04; REST deprecated/removed in newer releases |
| API versions | [TrueNAS API](https://api.truenas.com/) | выбираем API v25.10.5 и видим доступные версии |
| JSON-RPC protocol | [JSON-RPC 2.0 over WebSocket](https://api.truenas.com/v25.10/jsonrpc.html) | request/response/error/event model, IDs и WebSocket transport |
| API methods index | [API Methods v25.10.5](https://api.truenas.com/v25.10/api_methods.html) | полный список методов, query options, RBAC и jobs |
| iSCSI setup | [Adding iSCSI Block Shares](https://www.truenas.com/docs/scale/shares/iscsi/addingiscsishares/) | target, extent, initiator, portal и выбор zvol/zvol snapshot как device extent |
| iSCSI screens | [Block iSCSI Share Target Screens](https://www.truenas.com/docs/scale/scaleuireference/shares/iscsisharesscreens/) | связи target/extent/initiator/portal и структура UI |
| datasets/zvols/snapshots | [Datasets](https://www.truenas.com/docs/scale/datasets/) | разделы zvols и snapshots |
| zvol clone | [Adding and Managing Zvols](https://www.truenas.com/docs/scale/25.10/printview/scaletutorials/) | zvol, snapshot, clone и предупреждение о необратимом удалении |

## Зафиксированные методы API

Статус `docs-verified` означает, что метод и его схема найдены в официальной документации. Для API family `25.10` этот read-only allow-list также найден в live `/api/docs/current/` конкретного NAS. Это **не** означает выполнение JSON-RPC-вызова на NAS.

### Базовый transport/health

| Метод | Назначение | Статус |
|---|---|---|
| `core.ping` | минимальная проверка вызова API | `docs-verified` — [документ](https://api.truenas.com/v25.10/api_methods_core.ping.html) |
| `auth.login_with_api_key` | аутентификация backend WebSocket-сессии API key | `docs-verified`; ключ передаётся только из runtime secret — [документ](https://api.truenas.com/v25.10/api_methods_auth.login_with_api_key.html) |

### Read-only storage discovery

| Метод | Назначение | Статус |
|---|---|---|
| `pool.dataset.query` | чтение datasets/zvols и их metadata | `docs-verified` — [документ](https://api.truenas.com/v25.10/api_methods_pool.dataset.query.html) |
| `pool.snapshot.query` | чтение ZFS snapshots | `docs-verified` — [документ](https://api.truenas.com/v25.10/api_methods_pool.snapshot.query.html) |
| `iscsi.target.query` | чтение iSCSI targets | `docs-verified` — [документ](https://api.truenas.com/v25.10/api_methods_iscsi.target.query.html) |
| `iscsi.extent.query` | чтение iSCSI extents и backing device | `docs-verified` — [документ](https://api.truenas.com/v25.10/api_methods_iscsi.extent.query.html) |
| `iscsi.targetextent.query` | чтение associations target → extent → LUN | `docs-verified` — [документ](https://api.truenas.com/v25.10/api_methods_iscsi.targetextent.query.html) |

### Storage staging and existing extent update

| Метод | Назначение | Статус |
|---|---|---|
| `pool.snapshot.create` | создать snapshot исходного dataset, например `games/master-games` | `docs-verified`; применять только через mock и отдельный apply gate — [документ](https://api.truenas.com/v25.10/api_methods_pool.snapshot.create.html) |
| `pool.snapshot.clone` | создать clone полного диска в новый dataset/zvol | `docs-verified`; применять только через mock и отдельный apply gate — [документ](https://api.truenas.com/v25.10/api_methods_pool.snapshot.clone.html) |
| `iscsi.extent.update` | обновить `device/file` существующего extent, сохранив его имя, target association и LUN | `docs-verified`; fake workflow и read-back пройдены, live apply одной станции остаётся отдельным gate — [документ](https://api.truenas.com/v25.10/api_methods_iscsi.extent.update.html) |
| `pool.dataset.delete` | удалить один неактуальный dataset clone после retention-проверки | `docs-verified`; вызывается только отдельным cleanup apply gate с `recursive=false` и `force=false` — [документ](https://api.truenas.com/v25.10.0/api_methods_pool.dataset.delete.html) |

В текущей схеме пользователя новый extent создавать не нужно. Для каждого ПК
сохраняется существующий extent, а его поле `Device/File` переводится на
`zvol/<новый clone>` через `iscsi.extent.update`. TrueNAS сам добавляет `/dev`
при построении backend-устройства. `iscsi.targetextent.update`
не входит в разрешённый adapter workflow: association target → extent и LUN
остаются прежними. Документация указывает для update роль
`SHARING_ISCSI_EXTENT_WRITE`. Наличие метода не доказывает, что горячая замена
безопасна для Windows/iSCSI, поэтому `allow_hot_switch=false` остаётся политикой
по умолчанию.

## Что пока не считается проверенным

- Ответы JSON-RPC на конкретном TrueNAS.
- Фактические IDs и mapping target/extent на NAS.
- Реакция конкретной версии TrueNAS/Windows на hot switch.
- Полный runtime response/error contract на конкретном NAS.
- Безопасность операций при активном подключённом Windows LUN.

## Следующий документальный шаг

Перед read-only smoke check: закрыть временный внешний доступ к docs либо
ограничить его trusted network, подготовить API key только во внешней
runtime-конфигурации и отдельно согласовать `core.ping`/query-вызовы. Write
методы и live update существующего extent остаются запрещены до отдельного
one-station gate.
