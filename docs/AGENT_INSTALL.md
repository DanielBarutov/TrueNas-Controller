# Инструкция установки Windows-агента

Для нового клиентского ПК сначала используйте короткий сценарий
[`docs/AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md): он собирает данные одним
stdlib-only Python-скриптом и заполняет форму station в UI. Текущая инструкция
ниже описывает ручной recovery-путь и отдельные проверки Windows Service.

Инструкция предназначена для staging-проверки текущего agent slice. Она не
заменяет фактическую Windows-проверку `LocalSystem`, ACL и heartbeat: эти
runtime-проверки остаются отдельным gate.

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
- elevated PowerShell для enrollment и регистрации службы;
- согласованные `station_id`, `agent_uuid` и agent version. Public key для
  подписанных команд нужен только если требуется удалённый refresh.

В production enrollment выполняется elevated-оператором, а служба работает от
встроенной учётной записи `LocalSystem`. Credential защищается DPAPI
machine-scope, а ACL файла разрешает доступ только `SYSTEM` и локальным
администраторам. Поэтому пароль обычного Windows-пользователя для службы не
нужен.

Перед установкой Controller должен быть запущен с внешним
`BASIC_AUTH_PASSWORD`, а оператор должен отдельно решить вопрос применения
baseline Alembic migration. Пароль, TrueNAS API key и private signing key в
эту инструкцию не записываются.

Для текущего Docker Compose используйте `$ControllerUrl =
"http://<controller-ip>:8000"`; автоматический installer дополнительно требует
`--allow-insecure-http`. В production используйте HTTPS без этого флага.

### Важно про LocalSystem

У `LocalSystem` нет пароля: SCM запускает службу напрямую от встроенной
системной учётной записи. Это не пароль Basic Auth Controller и не enrollment
token. Команда installer больше не запрашивает пароль Windows.

Компромисс: локальный администратор имеет доступ к machine-scope credential.
Агент не получает TrueNAS API key, а credential остаётся ограничен этим
клиентом и его station binding.

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
$CredentialPath = Join-Path $ProjectRoot "agent.credential"
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

## 5. Выполнить enrollment elevated-оператором

Открыть elevated PowerShell. Служба позже будет работать от `LocalSystem`, поэтому
enrollment не нужно выполнять под отдельной Windows-учётной записью.

Token вводится открыто и передаётся только текущему процессу. Он не попадает в
аргументы командной строки и после enrollment удаляется из переменной процесса:

```powershell
Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$env:AGENT_ENROLLMENT_TOKEN = $null

& $Python -m agent.entrypoint check-credential-store
if ($LASTEXITCODE -ne 0) {
    throw "Local protected credential store check failed; token was not used"
}

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

Повторный запуск при уже существующем credential проверит/перепривяжет его к
machine-scope и не делает новый сетевой enrollment. Это нужно для обновления
агента со старой user-scope схемы. Не читать credential через `Get-Content` и
не копировать его в другой каталог.

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

Команда `install` переводит службу на `LocalSystem` и не запрашивает пароль.
Credential загружается только при фактическом запуске процесса службы.

Проверить конфигурацию:

```powershell
sc.exe qc TrueNasControllerAgent
Start-Service -Name TrueNasControllerAgent
Get-Service -Name TrueNasControllerAgent
```

Если переменные окружения изменялись после регистрации службы, службу нужно
перезапустить. Не копировать credential и не добавлять его в переменные
окружения или аргументы командной строки.

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
`AGENT_API_BASE_URL`, `AGENT_STATION_ID`, путь credential и режим `LocalSystem`.

### Диагностика ошибки запуска 1053

Не используйте `python ... debug` как основной способ диагностики: стандартный
`pywin32`-обработчик `debug` запускает отдельный `pythonservice.exe` и на Windows
может скрыть traceback за сообщением «Синтаксическая ошибка в имени файла,
имени папки или метке тома».

Запустите агент в foreground-режиме из его установленной папки:

```powershell
$ProjectRoot = "C:\ProgramData\TrueNasController\agent"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Runner = Join-Path $ProjectRoot "scripts\windows_agent_service.py"
Set-Location $ProjectRoot
& $Python $Runner foreground
```

Команда должна занять текущую консоль. Остановите её через `Ctrl+C`. Если
конфигурация, DPAPI или credential недоступны, полный traceback будет выведен
в консоль. Для проверки только защищённого хранилища используйте:

```powershell
& $Python -m agent.entrypoint check-credential-store
```

После исправления ошибки остановите foreground-процесс и перезапустите службу:

```powershell
Restart-Service -Name TrueNasControllerAgent
Get-Service -Name TrueNasControllerAgent
```

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

## 9. Остановка и удаление агента

Обычная остановка:

```powershell
Stop-Service -Name TrueNasControllerAgent
```

Удаление локальной регистрации агента после остановки:

```powershell
Set-Location $ProjectRoot
& $Python -m agent.entrypoint remove
```

Не удалять credential до остановки службы. При re-enrollment не использовать
старый token: Controller помечает token использованным.

Удаление station из Controller выполняется оператором в UI:

1. Откройте **Станции и агенты**.
2. Нажмите **Удалить** в строке станции и подтвердите действие.
3. Controller скрывает station из активного реестра, удаляет agent binding и
   ожидающие команды, отзывает enrollment tokens, но сохраняет snapshots и
   историю publish.
4. Старый agent credential сразу перестаёт работать. Удаление в Controller не
   может физически удалить Windows Service на клиентском ПК: остановите службу
   и выполните локальную команду `agent.entrypoint remove` при необходимости.

Если нужно повторить установку на том же ПК, вставьте тот же
`station-report.json` в форму создания station. Soft-deleted запись будет
восстановлена с тем же стабильным UUID, а Controller выдаст новый token.
Старый credential и старый token использовать нельзя.

## Частые ошибки

| Симптом | Проверка |
|---|---|
| heartbeat работает, но refresh-команда не выполняется | передайте public key через `--command-verify-key` или `AGENT_COMMAND_VERIFY_KEY`; без него refresh намеренно отключён |
| `agent credential is missing` | выполнить enrollment elevated-оператором в тот же путь |
| `protected Windows credential store is unavailable` | команда запущена не на Windows; plaintext fallback для production запрещён |
| `credential file ACL setup failed while trying to resolve protected Windows principals` | обновить checkout и проверить pywin32; installer применяет ACL для `SYSTEM` и локальных администраторов до записи credential |
| `No module named win32service` при регистрации службы | обновить checkout и повторить installer: SCM запускается из target `.venv`, внешний `py -3` не используется для pywin32 |
| ошибка SCM `1069`/`1385` при запуске службы | повторить `install`: служба должна быть переведена на `LocalSystem`; пароль Windows не используется |
| ошибка SCM `1053` или `7009` | сначала запустить foreground-режим из инструкции выше; он показывает ошибку до запуска heartbeat |
| HTTP 409 при enrollment | token просрочен или уже использован; получить новый |
| HTTP 401 на heartbeat | credential/station binding не совпадает или credential отозван |
| станция offline | проверить службу, URL Controller, порт `8000` для локального HTTP, firewall и timestamp/часы Windows |
| команда не создаётся | Controller не собран с `AGENT_COMMAND_SIGNING_PRIVATE_KEY` |

После проверки удалить временные переменные `$EnrollmentToken`, `$Headers`,
`$OperatorCredential` и закрыть PowerShell-сессию.
