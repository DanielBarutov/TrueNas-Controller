# Установка агента на клиентский ПК

## Рекомендуемый порядок

Для нового клиента сначала сформируй отчёт через
`scripts/agent_station_report.py`, создай station в UI, а затем запусти
`scripts/install_windows_agent.py`. Он сам ставит зависимости, выполняет
enrollment с открытым вводом token, регистрирует службу и проверяет её запуск.

Ручной порядок ниже используй только для recovery или диагностики.

## Ручной порядок

1. В Controller создай station с ролью `client` или `admin`.
2. Сохрани одноразовый enrollment token только в защищённом канале.
3. На Windows-клиенте задай `AGENT_API_BASE_URL`, `AGENT_STATION_ID`,
   `AGENT_UUID`, `AGENT_VERSION`, `AGENT_HOSTNAME` и
   `AGENT_CREDENTIAL_PATH`. `AGENT_COMMAND_VERIFY_KEY` необязателен: это
   публичный ключ проверки подписанных refresh-команд.
4. Выполни enrollment из elevated PowerShell. Windows Service работает от
   `LocalSystem`, поэтому пароль Windows не нужен. В автоматическом сценарии
   передай `--report
   C:\Install\station-report.json`: station UUID берётся из отчёта. Installer
   сначала проверяет локальные DPAPI/ACL и только после успешной проверки
   просит одноразовый token.

```powershell
Set-Location C:\ProgramData\TrueNasController\agent
$env:AGENT_ENROLLMENT_TOKEN = $null
$Python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
& $Python -m agent.entrypoint check-credential-store
if ($LASTEXITCODE -ne 0) { throw "Local protected credential store check failed" }
$env:AGENT_ENROLLMENT_TOKEN = Read-Host "One-shot enrollment token (visible)"
& $Python -m agent.entrypoint enroll
Remove-Item Env:AGENT_ENROLLMENT_TOKEN
```

Token вводится видимо только в локальном PowerShell. Никогда не вставляй token или credential в issue,
лог, README или frontend.

## Credential и LocalSystem

Windows production store использует DPAPI machine scope и ACL только для
`SYSTEM` и локальных администраторов. Installer больше не запрашивает пароль
Windows и регистрирует службу от `LocalSystem`. Старый user-scope credential при
повторной установке автоматически перепротектится в machine-scope. Локальный
администратор сможет получить machine-scope credential — это осознанный
компромисс passwordless-сценария. Private signing key на клиент не устанавливается.
Если preflight сообщает об ошибке определения защищённых Windows principals,
нужна актуальная копия checkout и рабочий `pywin32`; одноразовый token до
успешного preflight не запрашивается.

## Регистрация службы

Из стабильной папки проекта выполни в elevated PowerShell:

```powershell
python -m agent.entrypoint install
```

В `services.msc` проверь, что `TrueNAS Controller Agent` работает от
`LocalSystem`, и запусти службу. Полная инструкция находится в
`docs/AGENT_INSTALL.md`.

Если служба завершается с ошибкой 1053/7009, не используй встроенный pywin32
`debug`: запусти агент в консоли из установленной папки:

```powershell
$Python = "C:\ProgramData\TrueNasController\agent\.venv\Scripts\python.exe"
$Runner = "C:\ProgramData\TrueNasController\agent\scripts\windows_agent_service.py"
& $Python $Runner foreground
```

Останови проверку через `Ctrl+C`. Foreground-режим показывает traceback
конфигурации/DPAPI и не выводит credential.
