# Windows-agent deployment boundary

Пошаговая staging-инструкция находится в
[`AGENT_INSTALL.md`](AGENT_INSTALL.md).

Документ описывает только подготовленный безопасный flow. Реальная Windows
регистрация службы, запуск от service account и запрос к controller выполняются
отдельным операторским smoke/integration gate и не считаются пройденными этим
репозиторием.

## Секреты и конфигурация

Не записывать в git, README, unit-файлы, логи или аргументы командной строки:

- `AGENT_ENROLLMENT_TOKEN` — одноразовый токен первичной регистрации;
- `AGENT_COMMAND_VERIFY_KEY` — публичный ключ проверки команд можно передавать
  через защищённую runtime-конфигурацию, но private key остаётся только на
  controller;
- agent credential, `BASIC_AUTH_PASSWORD` и TrueNAS API key.

Минимальный набор переменных для одноразовой регистрации:

```text
AGENT_API_BASE_URL=https://controller.example
AGENT_STATION_ID=<station-uuid>
AGENT_UUID=<new-agent-uuid>
AGENT_VERSION=0.1.0
AGENT_HOSTNAME=CLIENT-01
AGENT_CREDENTIAL_PATH=C:\ProgramData\TrueNasController\agent.credential
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

В Windows production factory использует DPAPI user scope и ограничивает ACL
credential-файла текущей учётной записью. Поэтому enrollment должен выполняться
под той же учётной записью, под которой впоследствии будет работать служба.
Фактический service account и его права остаются отдельным незакрытым gate.

## Windows Service

После успешного enrollment pywin32-команды передаются в Windows Service
Control Manager:

```powershell
python -m agent.entrypoint install
python -m agent.entrypoint start
```

Для остановки и удаления используются соответствующие команды `stop` и
`remove`. Перед production запуском нужно проверить, что служба читает тот же
credential store, имеет доступ к конфигурации и запускается под согласованной
service account. В Linux/CI эти команды намеренно завершаются без попытки
обратиться к SCM.

## Что проверено в репозитории

- one-shot coordinator и повторный запуск без повторного gateway call;
- fail-closed конфигурация UUID/token;
- защищённый atomic credential store, DPAPI и Windows ACL boundaries;
- композиция `enroll`/SCM entrypoint через injected Protocol boundaries;
- unit-тесты без внешнего controller, Windows SCM, Redis, PostgreSQL и TrueNAS.

Открыты: production installer, фактический service account, opt-in API↔agent
integration test и применение baseline Alembic migration.
