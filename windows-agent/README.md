# Native Windows Agent

Нативный агент — self-contained .NET Worker Service для Windows x64. Он
сохраняет существующий Controller contract:

- `POST /api/v1/agents/enroll` с одноразовым enrollment token;
- `POST /api/v1/agents/bootstrap` с одноразовым provisioning token, который
  может создать station автоматически;
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

Для текущего Windows-теста уже подготовлен self-contained `win-x64` файл
[`TrueNasControllerAgent.exe`](../TrueNasControllerAgent.exe) в корне
репозитория. После `git pull` его можно сразу копировать на клиентский ПК;
локальная сборка через .NET SDK для этого теста не требуется.

## Установка клиента

Скопируйте exe в `C:\Install`, затем из elevated PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path C:\Install | Out-Null
# Выполнить в каталоге, куда скопирован TrueNasControllerAgent.exe:
Set-Location C:\Install
.\TrueNasControllerAgent.exe report --output .\station-report.json
```

Каталоги `%LOCALAPPDATA%\TrueNasController\agent` и
`%ProgramData%\TrueNasController\agent` создаются EXE автоматически. Вручную
создавать их не нужно.

В Controller UI откройте **Станции и агенты** и создайте provisioning token.
Station вручную создавать не нужно: сервер возьмёт стабильный UUID из native
identity, создаст client station и сразу зарегистрирует агент. Report можно
сохранить для оператора, но для установки он больше не обязателен:

```powershell
.\TrueNasControllerAgent.exe install `
  --controller-url "http://192.168.0.47:8000" `
  --allow-insecure-http
```

В production используйте HTTPS и уберите `--allow-insecure-http`. Provisioning
token будет запрошен видимым `Console.ReadLine`; он не находится в аргументах,
файле или machine environment. Можно передать его явно через
`--provisioning-token`, но для истории команд предпочтителен видимый prompt.
Повторный запуск с существующим credential пропускает
enrollment только после успешной проверки credential heartbeat-запросом для
текущей station. Если credential относится к другой/удалённой station или
сервер возвращает `401`, installer очистит его и запросит новый видимый token.

Старый ручной сценарий остаётся совместимым: если station уже создана
оператором, передайте `--enrollment-token` вместо provisioning token. Эти два
режима нельзя смешивать.

Перед изменениями можно выполнить `install ... --dry-run`. Не передавайте
`--station-id`: UUID берётся из сохранённой native identity. `--report` остаётся
совместимым параметром для старого сценария и явно проверяется на совпадение
station/agent UUID.

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
- Повторная установка не доверяет одному наличию `agent.credential`: binding
  проверяется на Controller до пропуска enrollment.
- Публичный verify key опционален: без него heartbeat работает, но команды
  Controller не исполняются.
