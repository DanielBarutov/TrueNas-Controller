# План 37. Native agent EXE

## Цель

Оставить на клиентском Windows-ПК только self-contained
`TrueNasControllerAgent.exe`. EXE сам формирует совместимый station report в
JSON и выполняет bootstrap по одноразовому provisioning token, без Python и
без передачи Basic Auth.

## Контракт запуска

```powershell
.\TrueNasControllerAgent.exe report
.\TrueNasControllerAgent.exe install --controller-url "https://controller"
```

`report` печатает только JSON в stdout. `install` может использовать report из
файла для обратной совместимости, но при отсутствии `--report` создаёт его в
памяти, повторно использует стабильный UUID и запрашивает provisioning token
видимым вводом.

## Чекап

- [x] source report stdout оставляет JSON в stdout, status уходит в stderr;
- [x] install без Python/`--report` использует provisioning endpoint;
- [x] self-contained win-x64 EXE пересобран из обновлённого source;
- [ ] Windows smoke выполняется пользователем на клиентском ПК.
