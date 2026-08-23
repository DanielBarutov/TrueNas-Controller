# 26. Transactional outbox и retry semantics

## Цель

Устранить gap между commit состояния `publishing` и доставкой Dramatiq
сообщения. Состояние job и outbox event должны фиксироваться одной короткой
транзакцией, а relay — безопасно повторять отправку по event/idempotency key.

## Scope следующего подшага

- таблица `outbox_events` с event ID, aggregate/job ID, type, payload без
  секретов, status, attempts и timestamps;
- application `OutboxRepository` через `Protocol`;
- dispatch записывает outbox event в той же транзакции, а не вызывает queue
  напрямую;
- отдельный Dramatiq relay читает pending events, отправляет минимальный task и
  помечает event dispatched;
- retry/backoff и unknown broker outcome не меняют job payload;
- lease/lock не допускает одновременную отправку одного event несколькими relay.

## Ключевые тесты

- job state + outbox commit атомарны;
- rollback не оставляет outbox;
- relay отправляет IDs/idempotency/correlation без secrets;
- duplicate delivery безопасна для worker handler;
- retry increments attempts and preserves event;
- relay не удерживает database transaction вокруг network send.

## Запреты

Не подключать production Redis/NAS, не запускать storage write/destroy, не
класть mapping/API key/password в outbox payload.

## Статус

- [x] gap и scope зафиксированы;
- [ ] outbox model/repository созданы;
- [ ] relay и retry policy созданы;
- [ ] ключевые tests созданы;
- [ ] `STATE.md` обновлён.
