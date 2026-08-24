# Быстрый onboarding Windows-клиента

Для первичного добавления клиентского ПК используется один файл
`scripts/agent_station_report.py`. Это безопасный отчётчик на стандартной
библиотеке Python: он не устанавливает службу, не подключается к Controller и
не запрашивает пароль, Basic Auth, enrollment token или credential.

## 1. Получить отчёт на клиентском ПК

Скопируйте на Windows-ПК только файл `agent_station_report.py` в каталог
`C:\Install`. Нужен Python 3.12+; внешние зависимости не требуются. Запустите
PowerShell и сначала перейдите именно в этот каталог:

```powershell
New-Item -ItemType Directory -Force -Path C:\Install | Out-Null
Set-Location C:\Install
py -3 .\agent_station_report.py | Out-File -Encoding utf8 .\station-report.json
```

Передайте файл `C:\Install\station-report.json` оператору по согласованному
внутреннему каналу. Не редактируйте `station.station_id` и `agent.agent_uuid`:
это один и тот же стабильный UUID, который сохраняется локально
в `%LOCALAPPDATA%\TrueNasController\agent\identity.json`, чтобы повторный
запуск не создал другую identity.

В отчёте есть:

- поля `station.display_name`, `station.hostname` и `station.role` для формы
  создания station;
- общий `station.station_id`/`agent.agent_uuid` и `agent.agent_version` для
  создания station и последующего enrollment;
- справочные IP/MAC и состояние диска `D:`.

## 2. Создать station на админском ПК

1. Откройте Controller UI → **Станции и агенты**.
2. Откройте `C:\Install\station-report.json`, скопируйте JSON и вставьте его
   в поле **Отчёт с клиентского ПК**.
3. Нажмите **Подставить данные отчёта** и проверьте hostname, роль и UUID.
4. Нажмите **Создать station**.
5. Передайте показанный один раз enrollment token обратно на тот же клиентский
   ПК по защищённому каналу.

Basic Auth оператора и пароль Controller не передаются клиентскому скрипту.
Token имеет ограниченный TTL и после использования становится недействительным.

## 3. Установить и запустить агента одним сценарием

На клиентском ПК нужен согласованный checkout/release-пакет проекта и
установленный [uv](https://docs.astral.sh/uv/). Запустите elevated PowerShell
под той же Windows-учётной записью, под которой должна работать служба:

```powershell
Set-Location C:\Install\TrueNas-Controller
py -3 .\scripts\install_windows_agent.py `
  --controller-url "http://192.168.0.47:8000" `
  --report "C:\Install\station-report.json" `
  --allow-insecure-http
```

Для production с HTTPS укажите URL вида `https://controller.example` и уберите
`--allow-insecure-http`. Сценарий сам создаёт стабильную папку
`%ProgramData%\TrueNasController\agent`, устанавливает locked dependencies,
попросит открыто ввести одноразовый enrollment token и скрыто — пароль той же
service account, зарегистрирует и запустит службу. Token не попадает в аргументы
командной строки, постоянные машинные переменные или файлы.

`--station-id` здесь не нужен: installer читает общий UUID station/agent из
`station-report.json`.

`--command-verify-key` не нужен для первичной установки. Это публичный Ed25519
ключ Controller для проверки подписанной команды `refresh_process_snapshot`; он
не является enrollment token, Basic Auth-паролем или паролем Windows. Если его
не передать, heartbeat и статусы работают, а удалённая refresh-команда отключена.

Для проверки параметров без изменений используйте `--dry-run`. Для повторного
запуска уже enrolled агента token не запрашивается, если защищённый credential
на месте.

Адрес Controller API — не адрес TrueNAS `/api/docs`. Для текущего Docker Compose
это обычно `http://<ip-адрес>:8000`.

Подробности, troubleshooting и ручной recovery-путь остаются в
[`docs/AGENT_INSTALL.md`](AGENT_INSTALL.md).

Такое разделение сохраняет границу безопасности: клиентский ПК не получает
Basic Auth оператора, а одноразовый token появляется только после того, как
оператор проверил и создал station.

## 4. Удалить station и повторить enrollment

В разделе **Станции и агенты** кнопка **Удалить** скрывает station из активного
реестра, удаляет серверную agent-привязку и отзывает token. История snapshot
сохраняется, а Windows Service на клиентском ПК удалённо не удаляется.

После удаления тот же `station-report.json` можно снова вставить в форму:
Controller восстановит запись с прежним UUID и выдаст новый enrollment token.
