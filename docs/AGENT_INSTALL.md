# Инструкция установки Windows-агента

Для нового клиентского ПК сначала используйте короткий сценарий
[`docs/AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md): он собирает данные одним
stdlib-only Python-скриптом и заполняет форму station в UI. Текущая инструкция
ниже описывает ручной recovery-путь и отдельные проверки Windows Service.

Инструкция предназначена для staging-проверки текущего agent slice. Она не
не заменяет фактическую Windows-проверку service account и ACL: эти runtime
проверки остаются отдельным gate.

Агент подключается к собственному Controller API и не обращается напрямую к
TrueNAS. Поэтому `AGENT_API_BASE_URL` — это URL Controller без `/api/docs` и
без `/api` в конце. Адрес TrueNAS docs вроде `213.108.6.24/api/docs` сюда
передавать нельзя.

## 1. Что нужно подготовить

- Windows-машина с Python 3.12 или 3.13;
- PowerShell от имени администратора для подготовки и регистрации службы;
- установленный [uv](https://docs.astral.sh/uv/);
- HTTPS-доступ от Windows-машины к Controller API; для локального Docker Compose
  допускается HTTP на порту `8000` только с явным `--allow-insecure-http`;
- стабильная папка проекта агента;
- отдельная Windows-учётная запись для службы, если это возможно;
- согласованные `station_id`, `agent_uuid` и agent version. Public key для
  подписанных команд нужен только если требуется удалённый refresh.

В production enrollment и служба должны работать под одной и той же учётной
записью. Credential защищается DPAPI user scope и ACL текущего пользователя;
если enrollment выполнить под администратором, а службу запустить под другим
пользователем, служба не сможет расшифровать credential.

Перед установкой Controller должен быть запущен с внешним
`BASIC_AUTH_PASSWORD`, а оператор должен отдельно решить вопрос применения
baseline Alembic migration. Пароль, TrueNAS API key и private signing key в
эту инструкцию не записываются.

Для текущего Docker Compose используйте `$ControllerUrl =
"http://<controller-ip>:8000"`; автоматический installer дополнительно требует
`--allow-insecure-http`. В production используйте HTTPS без этого флага.

## 2. Создать station и получить одноразовый token

Выполнить в PowerShell администратора или оператора. Пароль вводится через
защищённый prompt и не попадает в командную строку:

```powershell
$ControllerUrl = "https://<controller-host>"
$StationHostname = "CLIENT-01"

$OperatorCredential = Get-Credential -Message "Controller Basic Auth (admin)"
$NetworkCredential = $OperatorCredential.GetNetworkCredential()
$BasicBytes = [Text.Encoding]::ASCII.GetBytes(
    "{0}:{1}" -f $OperatorCredential.UserName, $NetworkCredential.Password
)
$Headers = @{
    Authorization = "Basic " + [Convert]::ToBase64String($BasicBytes)
}
$Body = @{
    display_name = $StationHostname
    hostname = $StationHostname
    role = "client"
} | ConvertTo-Json

$Registration = Invoke-RestMethod `
    -Uri "$ControllerUrl/api/v1/stations" `
    -Method Post `
    -Headers $Headers `
    -ContentType "application/json" `
    -Body $Body

$StationId = [Guid]$Registration.station_id
$EnrollmentToken = [string]$Registration.enrollment_token
Write-Host "Station: $StationId"
Write-Host "Enrollment expires: $($Registration.enrollment_expires_at)"

$Registration = $null
$NetworkCredential = $null
$BasicBytes = $null
```

Token действует ограниченное время и используется один раз. Не выводить
`$EnrollmentToken`, не сохранять ответ в файл и не отправлять token через
чат/issue tracker.

## 3. Подготовить проект агента

Для текущей проверки используется стабильная копия checkout. Финальный
пакет/инсталлятор будет добавлен отдельным production-подшагом.

```powershell
$ProjectRoot = "C:\ProgramData\TrueNasController\agent"
New-Item -ItemType Directory -Force -Path $ProjectRoot | Out-Null

# Скопировать сюда согласованный checkout проекта, затем:
Set-Location $ProjectRoot
uv sync
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Test-Path $Python
```

Не использовать рабочую папку вроде `Downloads` или временный каталог:
Windows Service должен ссылаться на неизменяемый согласованный путь.

## 4. Задать runtime-конфигурацию

В elevated PowerShell задать только несекретные параметры и, при необходимости,
public key на
уровне компьютера. `<...>` — placeholders, их нужно заменить своими
значениями; скобки не вводятся. Этот шаг можно выполнить в той же сессии, что
и шаг 2; если открыта новая сессия, присвоить `$StationId` фактическим UUID из
ответа Controller.

```powershell
$ControllerUrl = "https://<controller-host>"
$AgentUuid = [Guid]::NewGuid().Guid
$AgentVersion = "0.1.0"
$AgentHostname = "CLIENT-01"
$CredentialPath = "C:\ProgramData\TrueNasController\agent.credential"
$CommandVerifyKey = $null # optional: public key for signed refresh commands

[Environment]::SetEnvironmentVariable("AGENT_API_BASE_URL", $ControllerUrl, "Machine")
[Environment]::SetEnvironmentVariable("AGENT_STATION_ID", $StationId.Guid, "Machine")
[Environment]::SetEnvironmentVariable("AGENT_UUID", $AgentUuid, "Machine")
[Environment]::SetEnvironmentVariable("AGENT_VERSION", $AgentVersion, "Machine")
[Environment]::SetEnvironmentVariable("AGENT_HOSTNAME", $AgentHostname, "Machine")
[Environment]::SetEnvironmentVariable("AGENT_CREDENTIAL_PATH", $CredentialPath, "Machine")
[Environment]::SetEnvironmentVariable("AGENT_COMMAND_VERIFY_KEY", $CommandVerifyKey, "Machine")
[Environment]::SetEnvironmentVariable("AGENT_ALLOW_INSECURE_HTTP", $null, "Machine")
[Environment]::SetEnvironmentVariable("AGENT_ENROLLMENT_TOKEN", $null, "Machine")
```

`AGENT_COMMAND_VERIFY_KEY` — необязательный public key для проверки подписанной
команды refresh. Это не enrollment token и не пароль Basic Auth. Private key
`AGENT_COMMAND_SIGNING_PRIVATE_KEY` остаётся на Controller и никогда не
попадает на Windows-машину. Без public key heartbeat работает, но refresh-команды
отключены.

Если используется локальный HTTP Compose, в этом ручном варианте также задайте
`AGENT_ALLOW_INSECURE_HTTP` в Machine environment равным `1`; при HTTPS оставьте
переменную пустой или удалите её.

## 5. Выполнить enrollment под service account

Открыть PowerShell под той же учётной записью, под которой будет работать
служба. Убедиться, что эта учётная запись читает `$ProjectRoot` и может писать
в каталог `$CredentialPath`.

Token вводится открыто и передаётся только текущему процессу. Он не попадает в
аргументы командной строки и после enrollment удаляется из переменной процесса:

```powershell
Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EnrollmentToken = Read-Host "One-shot enrollment token (visible)"

try {
    $env:AGENT_ENROLLMENT_TOKEN = $EnrollmentToken

    & $Python -m agent.entrypoint enroll
    if ($LASTEXITCODE -ne 0) {
        throw "Agent enrollment failed with exit code $LASTEXITCODE"
    }
}
finally {
    Remove-Item Env:AGENT_ENROLLMENT_TOKEN -ErrorAction SilentlyContinue
    Remove-Variable EnrollmentToken -ErrorAction SilentlyContinue
}

if (-not (Test-Path $CredentialPath)) {
    throw "Protected credential file was not created"
}
Write-Host "Enrollment completed; credential content is not displayed."
```

Повторный запуск при уже существующем credential не делает новый сетевой
enrollment. Не читать credential через `Get-Content` и не копировать его в
другой каталог.

## 6. Зарегистрировать и настроить службу

В новой elevated PowerShell заново задать `$ProjectRoot` и `$Python`, затем из
`$ProjectRoot` выполнить:

```powershell
$ProjectRoot = "C:\ProgramData\TrueNasController\agent"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Set-Location $ProjectRoot
& $Python -m agent.entrypoint install
Get-Service -Name TrueNasControllerAgent
```

Команда `install` только регистрирует SCM boundary и не расшифровывает
credential. Credential загружается при фактическом запуске процесса службы,
уже под настроенной service account; поэтому регистрацию можно выполнять из
elevated administrator PowerShell.

Затем открыть `services.msc`, найти `TrueNAS Controller Agent` и на вкладке
`Log On` выбрать ту же service account, под которой выполнялся enrollment.
Учётной записи должно быть разрешено `Log on as a service`. `LocalSystem` не
использовать без отдельного обоснования.

После настройки учётной записи:

```powershell
sc.exe qc TrueNasControllerAgent
Start-Service -Name TrueNasControllerAgent
Get-Service -Name TrueNasControllerAgent
```

Если переменные окружения изменялись после регистрации службы, службу нужно
перезапустить. Не передавать пароль service account в `sc.exe` или в
аргументах командной строки; использовать UI/защищённый механизм Windows.

## 7. Проверить heartbeat

Heartbeat отправляется примерно раз в 10 секунд. Повторно создать Basic Auth
headers из шага 2 и выполнить read-only запрос:

```powershell
$Stations = Invoke-RestMethod `
    -Uri "$ControllerUrl/api/v1/stations" `
    -Method Get `
    -Headers $Headers

$Stations |
    Where-Object { $_.station_id -eq $StationId.Guid } |
    Select-Object station_id, hostname, status, enabled
```

Ожидаемое состояние после успешного heartbeat — `online`. Если станция не
появилась или осталась offline, сначала проверить `Get-Service`, HTTPS-доступ,
`AGENT_API_BASE_URL`, `AGENT_STATION_ID` и совпадение service account.

## 8. Проверить signed refresh command

Этот шаг возможен только если Controller запущен с private signing key, а
агент — с соответствующим public key. В новой PowerShell-сессии сначала
прочитать `ControllerUrl`, `StationId`, `AgentUuid` и Basic Auth headers заново;
Basic Auth headers используются те же:

```powershell
$CommandBody = @{
    name = "refresh_process_snapshot"
    ttl_seconds = 300
} | ConvertTo-Json

$Command = Invoke-RestMethod `
    -Uri "$ControllerUrl/api/v1/agents/$AgentUuid/commands" `
    -Method Post `
    -Headers $Headers `
    -ContentType "application/json" `
    -Body $CommandBody

$Command | Select-Object command_id, name, expires_at, status
```

Агент получит команду на следующем heartbeat, локально обновит process
snapshot и отправит acknowledgement. Shell, PowerShell и произвольный запуск
процессов этой командой не поддерживаются.

## 9. Остановка, удаление и re-enrollment

Обычная остановка:

```powershell
Stop-Service -Name TrueNasControllerAgent
```

Удаление регистрации после остановки:

```powershell
Set-Location $ProjectRoot
& $Python -m agent.entrypoint remove
```

Не удалять credential до остановки службы. При re-enrollment не использовать
старый token: Controller помечает token использованным. Для текущей версии
повторная регистрация с тем же `agent_uuid` требует отдельного решения по
старой binding записи; безопаснее заранее выдать новый UUID и новый
одноразовый token либо выполнить согласованную операторскую очистку.

## Частые ошибки

| Симптом | Проверка |
|---|---|
| heartbeat работает, но refresh-команда не выполняется | передайте public key через `--command-verify-key` или `AGENT_COMMAND_VERIFY_KEY`; без него refresh намеренно отключён |
| `agent credential is missing` | enrollment выполнен под той же учётной записью и в тот же путь |
| `protected Windows credential store is unavailable` | команда запущена не на Windows; plaintext fallback для production запрещён |
| HTTP 409 при enrollment | token просрочен или уже использован; получить новый |
| HTTP 401 на heartbeat | credential/station binding не совпадает или credential отозван |
| станция offline | проверить службу, URL Controller, порт `8000` для локального HTTP, firewall и timestamp/часы Windows |
| команда не создаётся | Controller не собран с `AGENT_COMMAND_SIGNING_PRIVATE_KEY` |

После проверки удалить временные переменные `$EnrollmentToken`, `$Headers`,
`$OperatorCredential` и закрыть PowerShell-сессию.
