# 34. Runtime worker и граница TrueNAS secret

## Цель

Замкнуть runtime-путь `dispatch → transactional outbox → Dramatiq →
executor`, который был покрыт acceptance-тестом, но отсутствовал в Compose.
Из-за этого UI видел `accepted`, а job оставалась на `0%`.

## Входы

- `DATABASE_URL` для чтения outbox и сохранения результата;
- `REDIS_URL` для Dramatiq broker;
- `worker/outbox_relay.py` и `worker/tasks.py`;
- текущий fake executor для локального/dry-run профиля.

## Выходы

- отдельный `worker` service в Compose;
- polling relay с lease/retry и Dramatiq consumer в одном Linux-процессе;
- параметры `WORKER_ID`, `WORKER_POLL_INTERVAL_SECONDS`,
  `DRAMATIQ_WORKER_THREADS`;
- явный `PUBLISH_EXECUTOR_MODE=fake` для текущего безопасного профиля;
- документированная граница: `TRUENAS_API_KEY` не используется текущим fake
  executor и не должен попадать во frontend или Windows-agent.

## Запреты

- не выполнять `pool.snapshot.create`, `pool.snapshot.clone` или
  `iscsi.targetextent.update`;
- не считать завершение fake executor фактическим изменением TrueNAS;
- не передавать API key через UI, agent или job payload.

## Реализация

- [x] Compose service ждёт `backend` health и `redis` health.
- [x] Runtime стартует Dramatiq Worker и регулярно забирает outbox.
- [x] Runtime создаёт свежий application handler/UoW на задачу.
- [x] Worker использует `NullPool`, чтобы asyncpg-соединение не переходило
  между event loop разных Dramatiq callbacks.
- [x] В embedded Dramatiq Worker отключён только Prometheus middleware,
  который требует CLI-only `after_process_boot`; retry/age/shutdown middleware
  сохранены.
- [x] Actor объявляется после `Worker.start()`, чтобы embedded worker успел
  подключить consumer к очереди `default`.
- [x] `dry_run` переводит fake job в terminal `completed` с причиной
  `dry_run_simulation`; UI явно называет результат симуляцией.
- [x] Fake executor остаётся единственным разрешённым режимом.
- [x] Ошибочная или неизвестная executor-конфигурация не принимается молча.
- [x] Добавлены key tests конфигурации worker и документация запуска.

## Открыто

- [ ] Реализовать и отдельно согласовать write-capable TrueNAS adapter.
- [ ] После adapter добавить `TRUENAS_WS_URL`/`TRUENAS_API_KEY` только в
  backend/worker runtime secret и провести read-only LAN smoke.
- [ ] Проверить реальный Compose worker на пользовательском ПК после pull.
