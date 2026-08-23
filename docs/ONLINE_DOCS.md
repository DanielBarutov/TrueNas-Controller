# Проверенные онлайн-документы TrueNAS

Последняя проверка: **2026-08-23**

## Зафиксированная версия

- Документация API: **TrueNAS API v25.10.5**.
- Документация продукта: ветка **TrueNAS SCALE 25.10**.
- Настройка в проекте: `TRUENAS_VERSION=25.10`.
- Текущая проверка выполнена по публичным официальным сайтам TrueNAS. Реальный NAS и его локальный `/api/docs/` не подключались.

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

Статус `docs-verified` означает, что метод и его схема найдены в официальной документации. Это **не** означает runtime-проверку на конкретном NAS.

### Базовый transport/health

| Метод | Назначение | Статус |
|---|---|---|
| `core.ping` | минимальная проверка вызова API | `docs-verified` — [документ](https://api.truenas.com/v25.10/api_methods_core.ping.html) |

### Read-only storage discovery

| Метод | Назначение | Статус |
|---|---|---|
| `pool.dataset.query` | чтение datasets/zvols и их metadata | `docs-verified` — [документ](https://api.truenas.com/v25.10/api_methods_pool.dataset.query.html) |
| `pool.snapshot.query` | чтение ZFS snapshots | `docs-verified` — [документ](https://api.truenas.com/v25.10/api_methods_pool.snapshot.query.html) |
| `iscsi.target.query` | чтение iSCSI targets | `docs-verified` — [документ](https://api.truenas.com/v25.10/api_methods_iscsi.target.query.html) |
| `iscsi.extent.query` | чтение iSCSI extents и backing device | `docs-verified` — [документ](https://api.truenas.com/v25.10/api_methods_iscsi.extent.query.html) |
| `iscsi.targetextent.query` | чтение associations target → extent → LUN | `docs-verified` — [документ](https://api.truenas.com/v25.10/api_methods_iscsi.targetextent.query.html) |

### Storage staging

| Метод | Назначение | Статус |
|---|---|---|
| `pool.snapshot.create` | создать один master snapshot на job | `docs-verified`; применять только через mock и отдельный apply gate — [документ](https://api.truenas.com/v25.10/api_methods_pool.snapshot.create.html) |
| `pool.snapshot.clone` | создать clone snapshot в новый dataset/zvol | `docs-verified`; применять только через mock и отдельный apply gate — [документ](https://api.truenas.com/v25.10/api_methods_pool.snapshot.clone.html) |

### Кандидат на mapping switch

| Метод | Назначение | Статус |
|---|---|---|
| `iscsi.targetextent.update` | обновить association по ID, включая target/extent/LUN | `docs-verified`, но **не разрешён к runtime apply** до mock-тестов, read-back и теста одной выделенной станции — [документ](https://api.truenas.com/v25.10/api_methods_iscsi.targetextent.update.html) |

Документация указывает для этого метода роль `SHARING_ISCSI_TARGETEXTENT_WRITE`. Наличие метода не доказывает, что горячее переключение безопасно для Windows/iSCSI, поэтому `allow_hot_switch=false` остаётся политикой по умолчанию.

## Что пока не считается проверенным

- Фактическая версия конкретного TrueNAS.
- Фактические IDs и mapping target/extent на NAS.
- Реакция конкретной версии TrueNAS/Windows на hot switch.
- Полный runtime response/error contract на конкретном NAS.
- Безопасность операций при активном подключённом Windows LUN.

## Следующий документальный шаг

Перед реализацией adapter: открыть `https://<NAS_IP>/api/docs/` на согласованном NAS, сверить версии и имена методов, сохранить расхождения в этом файле и только после этого обновлять `method_registry.py`.
