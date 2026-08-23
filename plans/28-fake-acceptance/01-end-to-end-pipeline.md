# 28. End-to-end fake publish acceptance

## Цель

Проверить полный безопасный pipeline на локальном SQLite: создание draft,
server-side preflight/confirmation, dispatch в transactional outbox, relay,
worker handler и deterministic fake apply с persisted per-target verify.

## Сценарий

```text
Create draft
  → Prepare preflight + confirmation
  → Dispatch: publishing + outbox event
  → Relay: minimal payload
  → Handler reloads job/targets
  → Fake executor apply/verify
  → completed + target verified
```

Повторная доставка того же payload должна не создавать второй fake master или
clone после terminal `completed`.

## Ключевые проверки

- dynamic admin/client station IDs;
- no blocking preflight and explicit confirmation;
- outbox event dispatched without real broker;
- fake adapter creates one master/clone and persists independent verify;
- duplicate worker delivery is idempotent;
- response/state contains no credentials or external API key.

## Запреты

Не подключать production Redis, TrueNAS, WebSocket, real mapping switch,
destroy/cleanup или реальные storage objects.

## Статус

- [x] scenario зафиксирован;
- [x] acceptance test создан;
- [x] Ruff и pytest пройдены;
- [x] `STATE.md` обновлён.

Подшаг завершён. Полный SQLite/fake pipeline доказан от dynamic draft и
server-side confirmation до outbox relay, worker reload и persisted verified
target. Это не доказательство реального TrueNAS integration.
