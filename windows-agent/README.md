# Native Windows Agent

Нативный агент — self-contained .NET Worker Service для Windows x64. Он
сохраняет существующий Controller contract:

- `POST /api/v1/agents/enroll` с одноразовым enrollment token;
- `POST /api/v1/agents/heartbeat` с Bearer credential;
- `POST /api/v1/agents/commands/{command_id}/ack`;
- только подписанная команда `refresh_process_snapshot`.

Агент использует один и тот же стабильный UUID в `station-report.json` для
`station.station_id` и `agent.agent_uuid`. Credential хранится в DPAPI
machine-scope и доступен службе `LocalSystem`; Basic Auth оператора и пароль
Windows в native agent не передаются.

## Сборка release

Нужен .NET SDK 10. В PowerShell из корня репозитория:

```powershell
dotnet publish .\windows-agent\src\TrueNasController.Agent\TrueNasController.Agent.csproj `
  -c Release `
  -r win-x64 `
  --self-contained true `
  -p:PublishSingleFile=true `
  -o .\windows-agent\artifacts\win-x64
```

Для клиента передаётся файл:
`windows-agent\artifacts\win-x64\TrueNasControllerAgent.exe`.

## Установка клиента

Скопируйте exe в `C:\Install`, затем из elevated PowerShell:

```powershell
Set-Location C:\Install
.\TrueNasControllerAgent.exe report --output .\station-report.json
```

Вставьте report в Controller UI, создайте station и передайте полученный token
на этот ПК. После этого:

```powershell
.\TrueNasControllerAgent.exe install `
  --controller-url "http://192.168.0.47:8000" `
  --report "C:\Install\station-report.json" `
  --allow-insecure-http
```

В production используйте HTTPS и уберите `--allow-insecure-http`. Token будет
запрошен видимым `Console.ReadLine`; он не находится в аргументах, файле или
machine environment. Повторный запуск с существующим credential не делает
новый enrollment.

Перед изменениями можно выполнить `install ... --dry-run`. Не передавайте
`--station-id`: UUID берётся из report и проверяется на совпадение.

## Проверка и диагностика

```powershell
Get-Service -Name TrueNasControllerAgent
sc.exe qc TrueNasControllerAgent

Set-Location C:\ProgramData\TrueNasController\agent
.\TrueNasControllerAgent.exe foreground --config .\agent.json
```

Команды `start`, `stop` и `remove` управляют локальной регистрацией службы.
Удаление station в Controller отзывает серверную привязку, но не может удалённо
удалить Windows Service.

## Design notes

- `AgentWorker` читает config и DPAPI credential только после входа service host
  в running state, чтобы сеть/диск/DPAPI не блокировали SCM startup (1053).
- Конфигурация хранится в `agent.json`, чтобы не зависеть от stale environment
  snapshot процесса `services.exe`.
- `WindowsServiceManager` вызывает SCM native API и не использует
  `pythonservice.exe`.
- Публичный verify key опционален: без него heartbeat работает, но команды
  Controller не исполняются.
