# Быстрый onboarding Windows-клиента

## Что делает скрипт

На клиентском ПК запускается `scripts/agent_station_report.py`. Это один файл
на стандартной библиотеке Python 3.12+, без установки пакетов и без доступа к
сети. Скрипт собирает hostname, IP/MAC, состояние `D:` и создаёт локальный
несекретный `agent_uuid`.

Он не содержит Basic Auth, пароль Controller, enrollment token или agent
credential. Поэтому файл можно передать клиенту отдельно от админского доступа.

## На клиентском ПК

Скопируйте файл на Windows и выполните в PowerShell:

```powershell
py -3 .\agent_station_report.py
```

Скопируйте JSON из консоли оператору. Для повторного запуска оставляйте файл
identity на месте: `%LOCALAPPDATA%\TrueNasController\agent\identity.json`.
Иначе будет создан новый UUID, который не совпадёт с последующим enrollment.

## На админском ПК

В разделе **Станции и агенты** вставьте JSON в блок **Отчёт с клиентского ПК**
и нажмите **Подставить данные отчёта**. UI заполнит поля `display_name`,
`hostname` и `role`, покажет UUID и позволит создать station.

После создания station Controller показывает одноразовый enrollment token.
Передайте его клиенту по защищённому каналу. Token ограничен по времени и
может быть использован только один раз.

## Что делать после создания station

Отчёт не регистрирует Windows Service автоматически. Для текущего staging
enrollment используйте [подробную инструкцию установки](../../../docs/AGENT_INSTALL.md):
укажите `AGENT_UUID` из отчёта, введите token только в процесс enrollment и
запускайте службу под той же учётной записью, под которой сохранён DPAPI
credential.

Не передавайте клиенту пароль Basic Auth и не вставляйте token в общий чат,
issue tracker или Markdown-файл.
