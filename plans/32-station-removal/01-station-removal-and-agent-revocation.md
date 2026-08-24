# 32. Удаление станции и агентской привязки

## Цель

Дать оператору явную операцию удаления station из активного реестра и
привязанного Windows-агента, не уничтожая диагностическую историю.

## Решение и инварианты

- `DELETE /api/v1/stations/{station_id}` требует Basic Auth и выполняет
  soft-delete станции: `deleted_at` заполняется, `enabled=false`, состояние
  становится `disabled`.
- Строка агента удаляется вместе с ожидающими командами. Старый credential
  после этого не проходит heartbeat.
- Все активные enrollment tokens станции отзываются.
- `process_snapshots` и `publish_targets` не удаляются: они нужны для истории и
  разбора ошибок.
- Повторное создание station с тем же стабильным UUID из
  `station-report.json` восстанавливает soft-deleted station, сохраняет историю
  и выдаёт новый одноразовый token.
- Удаление из Controller не удаляет Windows Service удалённо. Службу нужно
  остановить и удалить локально на клиентском ПК.

## Реализационный порядок

1. Расширить `StationRepository` и добавить application use case удаления.
2. В одной UoW-транзакции удалить agent/commands, отозвать tokens и soft-delete
   station.
3. Добавить Basic Auth DELETE route и подключить его в composition root.
4. Добавить UI-кнопку с подтверждением, обработку 204 и восстановление по тому
   же station report UUID.
5. Добавить ключевые application/API/frontend tests и обновить инструкции.

## Критерии проверки

- удалённая станция не возвращается из `GET /api/v1/stations`;
- агент и pending commands отсутствуют, token отозван, snapshots сохранены;
- старый credential отклоняется;
- повторное создание с тем же UUID восстанавливает запись и выдаёт новый token;
- DELETE без Basic Auth получает `401`, неизвестная станция — `404`;
- backend/frontend tests, Ruff и production build проходят.

## Статус

- [x] application port/use case и SQLAlchemy repository;
- [x] DELETE API и Basic Auth boundary;
- [x] operator UI с подтверждением удаления;
- [x] повторная регистрация по сохранённому station report UUID;
- [x] tests, Ruff и frontend build.
