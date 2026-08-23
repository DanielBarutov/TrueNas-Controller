# Установка агента на клиентский ПК

## Порядок

1. В Controller создай station с ролью `client` или `admin`.
2. Сохрани одноразовый enrollment token только в защищённом канале.
3. На Windows-клиенте задай `AGENT_API_BASE_URL`, `AGENT_STATION_ID`,
   `AGENT_UUID`, `AGENT_VERSION`, `AGENT_HOSTNAME`,
   `AGENT_CREDENTIAL_PATH` и `AGENT_COMMAND_VERIFY_KEY`.
4. Выполни enrollment под той же service account, под которой будет работать
   Windows Service:

```powershell
$env:AGENT_ENROLLMENT_TOKEN = "<one-shot-token>"
python -m agent.entrypoint enroll
Remove-Item Env:AGENT_ENROLLMENT_TOKEN
```

В рабочем процессе token нужно вводить скрыто, как описано в полном документе
`docs/AGENT_INSTALL.md`. Никогда не вставляй token или credential в issue,
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
