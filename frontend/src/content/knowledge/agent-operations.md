# Управление агентами с админского ПК

## Статусы

- `online` — heartbeat свежий;
- `stale` — heartbeat устарел, состояние Windows нельзя считать актуальным;
- `offline` — агент не отвечает;
- `disabled` — станция отключена оператором.

`offline` и `stale` нельзя трактовать как готовность к publish. Сначала
проверь службу, HTTPS-доступ, часы Windows и credential binding.

## Heartbeat и refresh

Агент отправляет process/drive snapshot примерно раз в 10 секунд. Browser не
читает процессы напрямую: он показывает данные, сохранённые Controller.
В process snapshot попадают доступные имя процесса, PID и путь к executable;
на сервере учитывается не более 512 процессов. Во время preflight Controller
сравнивает snapshot с политикой процессов и показывает в отчёте конкретные
совпадения, которые блокируют или предупреждают публикацию.

Команда refresh разрешена только в безопасном виде
`refresh_process_snapshot`. Она подписывается Controller, проверяется агентом,
не запускает shell/PowerShell и подтверждается после локального refresh.

В MVP команда создаётся через собственный API:

```text
POST /api/v1/agents/{agent_uuid}/commands
{
  "name": "refresh_process_snapshot",
  "ttl_seconds": 300
}
```

## Удаление station и агента

В UI откройте **Станции и агенты**, нажмите **Удалить** напротив станции и
подтвердите действие. Controller soft-delete-ит station, удаляет её agent
binding и ожидающие команды, отзывает enrollment tokens. История snapshots и
publish сохраняется. Старый credential перестаёт работать сразу.

Это серверная операция: Windows Service на клиентском ПК не удаляется по сети.
При полном удалении клиента сначала остановите службу, затем локально
выполните `python -m agent.entrypoint remove` из папки проекта.

Для повторной установки используйте тот же `station-report.json`: после
удаления Controller восстановит station по стабильному UUID и выдаст новый
одноразовый token.

## Если агент offline

1. Проверь `Get-Service -Name TrueNasControllerAgent`.
2. Проверь `AGENT_API_BASE_URL`: это URL Controller, не TrueNAS `/api/docs`.
3. Убедись, что credential читается службой от `LocalSystem`; production store
   использует DPAPI machine-scope и ACL для `SYSTEM`/локальных администраторов.
4. Проверь HTTPS и Windows Firewall.
5. Не удаляй credential и не повторяй enrollment старым token без решения
   оператора: token одноразовый, а agent UUID связан со station.
