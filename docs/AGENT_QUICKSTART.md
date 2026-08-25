# Быстрый onboarding Windows-клиента

Рекомендуемый путь использует один self-contained .NET-файл. На клиентском
ПК не нужны Python, uv, pywin32 и пароль Windows. Python-скрипты остаются в
репозитории только как legacy/recovery-вариант.

## 1. Получить station report на клиентском ПК

После `git pull` возьмите подготовленный
[`TrueNasControllerAgent.exe`](../TrueNasControllerAgent.exe) из корня проекта,
скопируйте его в `C:\Install` и запустите PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path C:\Install | Out-Null
# Если exe находится в текущем каталоге проекта:
# Copy-Item .\TrueNasControllerAgent.exe C:\Install\TrueNasControllerAgent.exe
Set-Location C:\Install
.\TrueNasControllerAgent.exe report --output .\station-report.json
```

Если native exe ещё не выдан и используется временный Python-report, команда
должна выполняться из той же папки, где лежит скрипт:

```powershell
Set-Location C:\Install
py -3 .\agent_station_report.py | Out-File -Encoding utf8 .\station-report.json
```

Не редактируйте `station.station_id` и `agent.agent_uuid`: это один стабильный
UUID. Native и Python report используют совместимый путь identity:
`%LOCALAPPDATA%\TrueNasController\agent\identity.json`.

Передайте `C:\Install\station-report.json` оператору. В отчёте нет Basic Auth,
enrollment token, credential или TrueNAS API key.

## 2. Выпустить provisioning token в Controller UI

1. Откройте Controller UI → **Станции и агенты**.
2. Нажмите **Создать provisioning token**.
3. Передайте показанный один раз token на тот же клиентский ПК.

Station вручную создавать не нужно: installer отправит серверу UUID из
`station-report.json`, и backend атомарно создаст client station и agent
binding. Операторский Basic Auth используется только в UI. Provisioning token
действует ограниченное время и используется один раз.

## 3. Установить native-агент на клиенте

Оставьте exe и report в `C:\Install`, откройте **PowerShell от имени
администратора** и выполните:

```powershell
Set-Location C:\Install
.\TrueNasControllerAgent.exe install `
  --controller-url "http://192.168.0.47:8000" `
  --report "C:\Install\station-report.json" `
  --allow-insecure-http
```

Для HTTPS укажите `https://controller.example` и уберите
`--allow-insecure-http`. Установка:

- копирует exe в `%ProgramData%\TrueNasController\agent`;
- сохраняет несекретный `agent.json`;
- просит provisioning token **видимым вводом** в текущей консоли;
- сохраняет credential через DPAPI machine-scope;
- регистрирует `TrueNasControllerAgent` как `LocalSystem` без пароля;
- запускает службу и ждёт её состояния `Running`.

Station UUID и agent UUID берутся из report и проверяются на совпадение. В
командной строке нет token, credential или пароля Windows.

Перед установкой можно проверить параметры без изменений:

```powershell
.\TrueNasControllerAgent.exe install `
  --controller-url "http://192.168.0.47:8000" `
  --report "C:\Install\station-report.json" `
  --allow-insecure-http `
  --dry-run
```

`--provisioning-token` — необязательный способ передать token явно; по умолчанию
installer спрашивает его видимым prompt. Для старого ручного сценария, где
station уже создана, используйте `--enrollment-token`.

`--command-verify-key` — необязательный URL-safe base64 public Ed25519 key для
подписанной команды `refresh_process_snapshot`. Это не token, не Basic Auth и
не пароль Windows. Без него обычные heartbeat продолжают работать.

## 4. Проверить и диагностировать

```powershell
Get-Service -Name TrueNasControllerAgent
sc.exe qc TrueNasControllerAgent
```

Для foreground-диагностики не нужен Python и не запускается `pythonservice.exe`:

```powershell
Set-Location C:\ProgramData\TrueNasController\agent
.\TrueNasControllerAgent.exe foreground --config .\agent.json
```

Остановите foreground через `Ctrl+C`. Рабочий процесс службы:

```powershell
.\TrueNasControllerAgent.exe stop
.\TrueNasControllerAgent.exe start
```

Heartbeat отправляется примерно раз в 10 секунд. Станция должна перейти в
`online` после первого успешного heartbeat.

## 5. Удаление

Удаление station в Controller выполняется оператором через UI: сервер отзывает
credential binding и токены, удаляет активную agent-привязку и сохраняет
историю snapshots. Удаление server-side не может физически остановить службу
на клиентском ПК.

На клиенте после удаления station выполните elevated:

```powershell
Set-Location C:\ProgramData\TrueNasController\agent
.\TrueNasControllerAgent.exe remove
```

Для повторного enrollment используйте тот же station report: Controller выдаст
новый token, старый token и старый credential использовать нельзя.

Подробный troubleshooting и legacy Python recovery находятся в
[`docs/AGENT_INSTALL.md`](AGENT_INSTALL.md), описание native-проекта — в
[`windows-agent/README.md`](../windows-agent/README.md).
