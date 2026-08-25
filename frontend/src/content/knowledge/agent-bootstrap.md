# Быстрый onboarding Windows-клиента

## На клиентском ПК

Передайте клиенту один self-contained файл `TrueNasControllerAgent.exe` и
выполните в PowerShell из папки, где он лежит:

```powershell
Set-Location C:\Install
.\TrueNasControllerAgent.exe report --output .\station-report.json
```

Команда не требует Python, uv или доступа к сети. Она сохраняет стабильный
UUID в `%LOCALAPPDATA%\TrueNasController\agent\identity.json` и печатает
безопасный JSON station/agent/network/drive report.

Передайте оператору файл `C:\Install\station-report.json`. Не изменяйте
`station.station_id` и `agent.agent_uuid`: это одна identity станции.

Если native exe временно недоступен, legacy-команда из той же папки:

```powershell
Set-Location C:\Install
py -3 .\agent_station_report.py | Out-File -Encoding utf8 .\station-report.json
```

## На админском ПК

В разделе **Станции и агенты** вставьте JSON в блок **Отчёт с клиентского ПК**,
нажмите **Подставить данные отчёта**, проверьте поля и создайте station. После
создания передайте клиенту одноразовый enrollment token. Basic Auth оператора
клиентскому exe не нужен и не передаётся.

## Установка одним native-сценарием

В elevated PowerShell клиента, из папки с exe и report:

```powershell
Set-Location C:\Install
.\TrueNasControllerAgent.exe install `
  --controller-url "http://192.168.0.47:8000" `
  --report "C:\Install\station-report.json" `
  --allow-insecure-http
```

Для HTTPS уберите `--allow-insecure-http`. Token вводится видимо и не
передаётся как аргумент. Служба устанавливается как `LocalSystem`, поэтому
пароль Windows не нужен. DPAPI machine-scope credential сохраняется в
`%ProgramData%\TrueNasController\agent\agent.credential`.

Параметры можно проверить без изменений через `--dry-run`. Public Ed25519 key
для signed refresh-команд задаётся отдельно через `--command-verify-key`; это
не token и не пароль.

## Проверка

```powershell
Get-Service -Name TrueNasControllerAgent
sc.exe qc TrueNasControllerAgent
```

Если служба не запускается, выполнить foreground без Python:

```powershell
Set-Location C:\ProgramData\TrueNasController\agent
.\TrueNasControllerAgent.exe foreground --config .\agent.json
```

## Удаление

После удаления station в Controller на клиенте выполнить elevated:

```powershell
Set-Location C:\ProgramData\TrueNasController\agent
.\TrueNasControllerAgent.exe remove
```

Это удаляет регистрацию службы. Повторный enrollment выполняется с тем же
report и новым token.
