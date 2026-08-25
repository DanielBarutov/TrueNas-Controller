# План 36 — TrueNAS write adapter: snapshot, clone и extent switch

## Цель

Создать изолированный versioned adapter для TrueNAS 25.10.x, который умеет
подготовить snapshot полного dataset `games/master-games`, сделать clone для
каждой выбранной станции и обновить `device/file` уже существующего extent на
новый zvol после отдельного safety gate.

## Последовательность операции

1. `pool.snapshot.create` для исходного dataset;
2. `pool.snapshot.clone` в уникальный dataset станции;
3. Найти старый extent выбранной станции и проверить его принадлежность;
4. `iscsi.extent.update` с сохранением настроек extent и заменой только
   `disk=zvol/<clone>` (для UI это поле `Device/File`; middleware TrueNAS
   использует `/dev/zvol/<clone>` внутри);
5. query/read-back и verify: association `target → extent` и LUN остаются теми же.

## Входы

- documented JSON-RPC method registry 25.10;
- существующий WebSocket/API-key transport и read-only DTO mapping;
- publish job source dataset и server-side station target/extent mapping.

## Выходы текущего подэтапа

- write-capable low-level adapter и Protocol ports;
- deterministic fake/contract tests на порядок вызовов и payload;
- `TRUENAS_APPLY_ENABLED=false` по умолчанию;
- worker wiring, station mapping read-back и fake acceptance добавлены;
  LAN smoke и live apply остаются отдельным gate.

## Запреты до отдельного согласования

- не подключаться к пользовательскому NAS из тестов;
- не выполнять `destroy/delete` storage objects;
- не обновлять реальный `device/file` extent;
- не включать live executor только из-за наличия `TRUENAS_API_KEY`.

## Чекап

- [x] registry и request schemas проверены по official docs;
- [x] adapter validates source dataset, extent ID и safe names;
- [x] fake/recording contract проверяет порядок вызовов и payload;
- [x] apply gate fail-closed;
- [x] после mock/read-back спроектирован и подключён wiring в Dramatiq worker;
  live apply остаётся выключенным до теста одной станции.
