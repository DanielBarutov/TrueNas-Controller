# 06.03 Native .NET Windows Agent

## Цель

Заменить проблемный Python/pywin32 runtime на self-contained .NET Worker
Service, сохранив существующий HTTP-контракт агента и стабильный UUID из
`station-report.json`.

## Границы

- native `win-x64` single-file executable;
- `report` без сети и секретов;
- `install` с видимым вводом one-shot enrollment token;
- DPAPI `LocalMachine` credential store и ACL для `SYSTEM`/Administrators;
- native SCM registration под `LocalSystem`;
- deferred config/DPAPI/network work после запуска service host;
- heartbeat, process snapshot, drive `D:` и signed `refresh_process_snapshot`;
- `foreground`, `start`, `stop`, `remove`, `--dry-run` для диагностики.

## Контракт совместимости

1. Report содержит один UUID в `station.station_id` и `agent.agent_uuid`.
2. Enrollment — `POST /api/v1/agents/enroll`.
3. Heartbeat — `POST /api/v1/agents/heartbeat` с Bearer credential.
4. Acknowledgement — `POST /api/v1/agents/commands/{command_id}/ack`.
5. Команды ограничены `refresh_process_snapshot`; произвольный shell/process
   launch отсутствует.

## Реализация

- [x] Domain records для config, report, heartbeat, commands и enrollment.
- [x] Controller HTTP client с HTTPS default и явным HTTP opt-in.
- [x] Network/process/drive collectors с fail-safe обработкой Windows access.
- [x] DPAPI credential store с atomic write и ACL.
- [x] Native SCM manager с `LocalSystem`, auto-start и диагностируемым Win32 error.
- [x] Worker Service с deferred startup и foreground режимом.
- [x] Ed25519 URL-safe base64 verifier с canonical command payload.
- [x] Self-contained installer и совместимый station report.
- [x] Frontend/docs переведены на native путь; Python оставлен legacy recovery.
- [x] Linux-side build прошёл через .NET 10 SDK.
- [ ] Windows client smoke: report → station → visible token → LocalSystem → heartbeat.
- [ ] Проверить обновление существующей Python установки и чтение старого
  machine-scope credential native агентом.
- [ ] После smoke решить, когда удалять/замораживать Python installer.

## Чекап

До закрытия плана запрещены заявления, что Windows Service runtime проверен:
Linux build не подтверждает работу SCM, DPAPI и ACL на Windows. Закрывающий
чекап выполняется на клиентском ПК и фиксируется в `STATE.md`.
