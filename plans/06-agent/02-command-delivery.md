# 06.02. Доставка подписанных команд агенту

## Цель

Доставить агенту только безопасную команду `refresh_process_snapshot` без
shell/PowerShell и произвольных аргументов. Команда должна переживать потерю
одного heartbeat-ответа, не выполняться повторно после ack и отклоняться при
подмене полей.

## Поток

```text
operator Basic Auth
        │ POST /api/v1/agents/{agent_uuid}/commands
        ▼
signed agent_commands row
        │ next heartbeat: short lease
        ▼
agent validates Ed25519 → local refresh → POST command ack
        │                         │
        └─ lease expiry ──────────┘ retry, no duplicate after ack
```

## Принятые решения

- подпись — Ed25519; controller держит private key только во внешней runtime
  конфигурации `AGENT_COMMAND_SIGNING_PRIVATE_KEY`, агенту нужен только public
  key;
- канонический envelope содержит protocol version, command UUID, name и
  `expires_at`; payload/аргументы команд отсутствуют;
- TTL команды по умолчанию 5 минут, максимум 15 минут;
- heartbeat выдаёт максимум 16 команд, lease длится 30 секунд;
- ack отправляется только после успешного локального refresh;
- повторный command UUID deduplicate-ится в процессе агента;
- неизвестные, просроченные и неподписанные команды отклоняются до execution.

## Выполнено

- domain envelope и deterministic signing payload;
- Ed25519 signer/verifier boundary;
- `agent_commands` ORM model и lease/ack repository;
- operator issue use case и Basic Auth route;
- heartbeat response parser и agent acknowledgement transport;
- Bearer-protected acknowledgement route;
- key tests для tampering, malformed response, lease retry, ack и auth.

## Production gates

- [x] сгенерировать baseline Alembic migration для `agent_commands` вместе с
  общей первой схемой; migration только создана, не применена автоматически;
- [x] добавить public key в agent runtime config и собрать composition root
  агента с `Ed25519CommandVerifier`;
- [x] добавить entrypoint, который загружает enrolled credential и собирает
  `PyWin32ServiceRuntime` без выполнения SCM-команд в Linux/CI;
- [ ] проверить Windows Service runtime под фактической service account;
- [ ] выполнить отдельный opt-in integration test собственного API и агента;
- [ ] не подключать TrueNAS, Redis и storage write для проверки этого потока.

## Проверки текущего среза

- `149 passed, 1 skipped` на Python 3.12/uv;
- Ruff check/format успешно;
- реальный Windows SCM, внешний agent network и production DB migration не
  запускались.
