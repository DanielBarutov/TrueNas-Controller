# Быстрый onboarding Windows-клиента

## Что делает скрипт

На клиентском ПК запускается `scripts/agent_station_report.py`. Это один файл
на стандартной библиотеке Python 3.12+, без установки пакетов и без доступа к
сети. Скрипт собирает hostname, IP/MAC, состояние `D:` и создаёт локальный
несекретный общий UUID `station.station_id` и `agent.agent_uuid`.

Он не содержит Basic Auth, пароль Controller, enrollment token или agent
credential. Поэтому файл можно передать клиенту отдельно от админского доступа.

## На клиентском ПК

Скопируйте файл в `C:\Install` на Windows и выполните в PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path C:\Install | Out-Null
Set-Location C:\Install
py -3 .\agent_station_report.py | Out-File -Encoding utf8 .\station-report.json
```

Передайте оператору файл `C:\Install\station-report.json`. Для повторного запуска оставляйте файл
identity на месте: `%LOCALAPPDATA%\TrueNasController\agent\identity.json`.
Иначе будет создан новый UUID, который не совпадёт с последующим enrollment.

## На админском ПК

В разделе **Станции и агенты** вставьте JSON в блок **Отчёт с клиентского ПК**
и нажмите **Подставить данные отчёта**. UI заполнит поля `display_name`,
`hostname`, `role` и передаст общий UUID для station/agent, после чего позволит
создать station.

После создания station Controller показывает одноразовый enrollment token.
Передайте его клиенту по защищённому каналу. Token ограничен по времени и
может быть использован только один раз.

## Установка одним сценарием

После создания station скопируйте согласованный checkout/release-пакет проекта
на Windows-клиент, установите `uv` и запустите elevated PowerShell под той же
учётной записью, под которой должна работать служба:

```powershell
Set-Location C:\Install\TrueNas-Controller
py -3 .\scripts\install_windows_agent.py `
  --controller-url "http://192.168.0.47:8000" `
  --report "C:\Install\station-report.json" `
  --allow-insecure-http
```

Для production с HTTPS замените URL на `https://controller.example` и уберите
`--allow-insecure-http`. Сценарий создаёт стабильную папку агента, устанавливает
зависимости, открыто запрашивает enrollment token и скрыто — пароль service
account, регистрирует службу и проверяет её состояние. Token не передаётся в аргументах
командной строки и не сохраняется.

`--station-id` не нужен: station UUID берётся из `station-report.json`.

В prompt после token вводится непустой пароль входа Windows для текущей
учётной записи службы. Это не пароль Basic Auth Controller. Если у Windows
пользователя нет пароля, сначала задайте его; passwordless-учётка не может
запустить эту службу и приводит к ошибке SCM `1069`.

`--command-verify-key` необязателен. Это публичный Ed25519-ключ Controller для
проверки подписанной команды refresh, а не enrollment token и не пароль. Без
него heartbeat работает, но удалённая refresh-команда отключена.
`--dry-run` проверяет параметры без изменений. Адрес Controller не должен быть
адресом TrueNAS `/api/docs`.

Если внешний `py -3` не видит `win32service`, обновите checkout и повторите
installer: актуальная версия регистрирует и запускает службу через target
`.venv\Scripts\python.exe`, где `uv sync` установил pywin32.

Ручной recovery-путь и troubleshooting описаны в
[подробной инструкции установки](../../../docs/AGENT_INSTALL.md).

Не передавайте клиенту пароль Basic Auth и не вставляйте token в общий чат,
issue tracker или Markdown-файл.
