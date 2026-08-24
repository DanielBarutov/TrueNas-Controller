# Быстрый onboarding Windows-клиента

Для первичного добавления клиентского ПК используется один файл
`scripts/agent_station_report.py`. Это безопасный отчётчик на стандартной
библиотеке Python: он не устанавливает службу, не подключается к Controller и
не запрашивает пароль, Basic Auth, enrollment token или credential.

## 1. Получить отчёт на клиентском ПК

Скопируйте на Windows-ПК только файл `agent_station_report.py`. Нужен Python
3.12+; внешние зависимости не требуются. Запустите PowerShell:

```powershell
py -3 .\agent_station_report.py
```

Скопируйте весь JSON из вывода и передайте его оператору по согласованному
внутреннему каналу. Не редактируйте `agent.agent_uuid`: он сохраняется локально
в `%LOCALAPPDATA%\TrueNasController\agent\identity.json`, чтобы повторный
запуск не создал другую identity.

В отчёте есть:

- поля `station.display_name`, `station.hostname` и `station.role` для формы
  создания station;
- `agent.agent_uuid` и `agent.agent_version` для последующего enrollment;
- справочные IP/MAC и состояние диска `D:`.

Если нужно сохранить результат в файл в Windows PowerShell 5.1, используйте
явную кодировку UTF-8:

```powershell
py -3 .\agent_station_report.py | Out-File -Encoding utf8 .\station-report.json
```

## 2. Создать station на админском ПК

1. Откройте Controller UI → **Станции и агенты**.
2. Вставьте JSON в поле **Отчёт с клиентского ПК**.
3. Нажмите **Подставить данные отчёта** и проверьте hostname, роль и UUID.
4. Нажмите **Создать station**.
5. Передайте показанный один раз enrollment token обратно на тот же клиентский
   ПК по защищённому каналу.

Basic Auth оператора и пароль Controller не передаются клиентскому скрипту.
Token имеет ограниченный TTL и после использования становится недействительным.

## 3. Завершить enrollment агента

Сам отчёт не является установщиком службы: это первый безопасный шаг, который
избавляет оператора от ручного сбора hostname/IP/MAC/D:. После получения token
выполните текущую подробную инструкцию из
[`docs/AGENT_INSTALL.md`](AGENT_INSTALL.md), начиная с подготовки проекта и
команды `agent.entrypoint enroll`. Для enrollment используйте `agent_uuid` из
того же отчёта, а не новый UUID.

Такое разделение сохраняет границу безопасности: клиентский ПК не получает
Basic Auth оператора, а одноразовый token появляется только после того, как
оператор проверил и создал station.
