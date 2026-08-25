# Установка агента на клиентский ПК

## Рекомендуемый native-путь

Native .NET agent — self-contained single-file Windows executable. На клиенте
не нужны Python, uv, pywin32 или пароль Windows. Сначала скопируйте exe в
`C:\Install`, затем выполняйте команды из этого каталога.

### Получить report

```powershell
Set-Location C:\Install
.\TrueNasControllerAgent.exe report --output .\station-report.json
```

Передайте JSON оператору. Вставьте его в Controller UI → **Станции и агенты**,
нажмите **Подставить данные отчёта** и создайте station. Используйте тот же
`station-report.json` при установке: он содержит общий UUID станции и агента.

### Установить службу

```powershell
Set-Location C:\Install
.\TrueNasControllerAgent.exe install `
  --controller-url "http://192.168.0.47:8000" `
  --report "C:\Install\station-report.json" `
  --allow-insecure-http
```

В production с HTTPS флаг `--allow-insecure-http` не используется. Token
вводится видимо в консоли только после проверки локального DPAPI preflight. В
аргументах и файлах не сохраняются token или credential. Служба работает от
`LocalSystem`, DPAPI использует machine scope, пароль Windows не запрашивается.

Не передавайте native agent Basic Auth оператора, NAS API key или private
signing key. `--command-verify-key` — только необязательный public key для
проверки подписанного `refresh_process_snapshot`.

### Диагностика и операции

```powershell
Get-Service -Name TrueNasControllerAgent
sc.exe qc TrueNasControllerAgent

Set-Location C:\ProgramData\TrueNasController\agent
.\TrueNasControllerAgent.exe foreground --config .\agent.json
```

Foreground запускайте вместо службы и останавливайте `Ctrl+C`. Дополнительные
команды: `.\TrueNasControllerAgent.exe start`, `stop`, `remove`.

### Удаление station и агента

Кнопка **Удалить** в UI удаляет активную server-side station/agent binding и
отзывает токены, но не может остановить Windows Service удалённо. После неё на
клиенте выполните elevated `remove`. Для повторной установки используйте тот
же report и новый token.

## Legacy Python recovery

Python installer и ручной `uv`-путь сохранены для совместимости со старыми
checkout. Они больше не являются рекомендуемым способом для нового клиента.
Подробности находятся в `docs/AGENT_INSTALL.md`.
