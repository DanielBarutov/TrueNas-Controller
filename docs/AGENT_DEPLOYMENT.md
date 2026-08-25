# Windows-agent deployment boundary

Для новых Windows-клиентов основной runtime — self-contained native .NET agent:
`windows-agent/src/TrueNasController.Agent`. Он публикуется одним exe, не
зависит от Python/uv/pywin32 и регистрирует службу через native SCM API. Полный
путь запуска находится в [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md).

```powershell
Set-Location C:\Install
.\TrueNasControllerAgent.exe report --output .\station-report.json
.\TrueNasControllerAgent.exe install `
  --controller-url "http://192.168.0.47:8000" `
  --allow-insecure-http
```

Token вводится видимо только в интерактивной консоли. Native agent использует
тот же enrollment/heartbeat/ack API, station UUID из native identity,
DPAPI machine-scope и `LocalSystem`. Python flow ниже сохранён как legacy
recovery и не является рекомендуемым новым способом установки.

Пошаговая staging-инструкция находится в
[`AGENT_INSTALL.md`](AGENT_INSTALL.md).

Документ описывает только подготовленный безопасный flow. Реальная Windows
регистрация службы `LocalSystem`, ACL и запрос к controller выполняются
отдельным операторским smoke/integration gate и не считаются пройденными этим
репозиторием.

## Секреты и конфигурация

Не записывать в git, README, unit-файлы, логи или аргументы командной строки:

- `AGENT_ENROLLMENT_TOKEN` — одноразовый токен первичной регистрации;
- `AGENT_COMMAND_VERIFY_KEY` — необязательный публичный ключ проверки команд;
  private key остаётся только на controller. Без него heartbeat работает, но
  подписанные refresh-команды отключены;
- agent credential, `BASIC_AUTH_PASSWORD` и TrueNAS API key.

Минимальный набор переменных для одноразовой регистрации:

```text
AGENT_API_BASE_URL=https://controller.example
AGENT_STATION_ID=<station-uuid>
AGENT_UUID=<new-agent-uuid>
AGENT_VERSION=0.1.0
AGENT_HOSTNAME=CLIENT-01
AGENT_CREDENTIAL_PATH=C:\ProgramData\TrueNasController\agent\agent.credential
AGENT_ENROLLMENT_TOKEN=<TOKEN>
```

`AGENT_ALLOW_INSECURE_HTTP=1` допустим только в локальной development-среде.
По умолчанию controller URL обязан быть HTTPS. После выполнения enrollment
переменную `AGENT_ENROLLMENT_TOKEN` нужно удалить из окружения.

## Одноразовый enrollment

Enrollment выполняется явной командой, а обычный путь процесса не пытается
регистрировать агент автоматически:

```powershell
python -m agent.entrypoint enroll
```

Команда сначала проверяет локальный credential store. Если защищённый
credential уже есть, повторный сетевой enrollment не выполняется. Если store
пуст, команда отправляет token, agent UUID, hostname и version на
`POST /api/v1/agents/enroll`, после чего сохраняет только полученный credential.
Token и credential не выводятся в stdout/stderr.

В Windows production factory использует DPAPI machine scope, а credential-файл
получает защищённый DACL только для `SYSTEM` и локальных администраторов.
Enrollment выполняется elevated-оператором, после чего служба запускается от
встроенной учётной записи `LocalSystem`; пароль Windows не нужен.
Локальный администратор сможет получить machine-scope credential — это осознанный
компромисс выбранного passwordless-сценария.

## Автоматический installer

Для нового клиента используйте
[`scripts/install_windows_agent.py`](../scripts/install_windows_agent.py). Он
принимает `station-report.json` и Controller URL,
затем:

1. копирует согласованный checkout в стабильный каталог;
2. выполняет `uv sync --locked --no-dev`;
3. записывает несекретные настройки на уровне компьютера;
4. проверяет локальные DPAPI/ACL до использования одноразового token;
5. вводит одноразовый token открытым prompt и выполняет enrollment;
6. регистрирует службу `LocalSystem` без запроса пароля и проверяет её запуск.

SCM-регистрация и запуск выполняются тем же `.venv\Scripts\python.exe`, куда
установлен `pywin32`; внешний Python, которым запущен installer, не обязан иметь
модуль `win32service`. `--dry-run` проверяет план без изменений. Скрипт должен
запускаться elevated. При наличии старого user-scope credential installer
перепротектит его в machine-scope без повторного enrollment.

## Windows Service

После успешного enrollment pywin32-команды передаются в Windows Service
Control Manager:

```powershell
$Python = "C:\ProgramData\TrueNasController\agent\.venv\Scripts\python.exe"
& $Python -m agent.entrypoint install
& $Python -m agent.entrypoint start
```

Для остановки и удаления используются соответствующие команды `stop` и
`remove`. Перед production запуском нужно проверить, что служба читает тот же
credential store и запускается под `LocalSystem`. В Linux/CI эти команды
намеренно завершаются без попытки
обратиться к SCM.

## Что проверено в репозитории

- one-shot coordinator и повторный запуск без повторного gateway call;
- fail-closed конфигурация UUID/token;
- защищённый atomic credential store, DPAPI и Windows ACL boundaries;
- композиция `enroll`/SCM entrypoint через injected Protocol boundaries;
- unit-тесты без внешнего controller, Windows SCM, Redis, PostgreSQL и TrueNAS.

Открыты: фактическая Windows-проверка `LocalSystem`/ACL, opt-in API↔agent
integration test и применение baseline Alembic migration.
