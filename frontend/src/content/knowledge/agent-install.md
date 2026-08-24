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
4. Выполни enrollment под той же service account, под которой будет работать
   Windows Service. В автоматическом сценарии передай `--report
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

## Credential и service account

Windows production store использует DPAPI user scope и ACL текущей учётной
записи. Enrollment под администратором и запуск службы под другим пользователем
приведут к ошибке расшифровки. Private signing key на клиент не устанавливается.

## Регистрация службы

Из стабильной папки проекта выполни в elevated PowerShell:

```powershell
python -m agent.entrypoint install
```

В `services.msc` выбери `TrueNAS Controller Agent`, укажи ту же service
account и только после этого запусти службу. Полная инструкция находится в
`docs/AGENT_INSTALL.md`.
