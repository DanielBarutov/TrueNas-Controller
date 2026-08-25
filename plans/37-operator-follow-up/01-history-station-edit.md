# План 37. История обновлений и редактирование станций

## Цель

Сделать историю обновлений пригодной для ежедневной работы оператора: по
умолчанию показывать последние 10 jobs, открывать подробности конкретной
операции и редактировать операторские поля станции и её TrueNAS mapping.

## Контракт

- `GET /api/v1/publish/jobs` по умолчанию возвращает 10 последних jobs;
- `GET /api/v1/publish/jobs/{job_id}` отдаёт timestamps, причину результата,
  per-target preflight/switch/verify и безопасные old/new mapping;
- UI показывает кнопку «Подробнее» без раскрытия секретов;
- `PATCH /api/v1/stations/{station_id}` редактирует display name, hostname,
  роль и enabled-политику;
- `PATCH /api/v1/stations/{station_id}/storage-mapping` сохраняет mapping
  существующего target/extent, не создавая storage-объекты.

## Чекап

- [x] Python schema/query/repository и migration обновлены;
- [x] UI history details, station edit и mapping edit добавлены;
- [x] dry-run по умолчанию `false` согласован на API, domain, БД и frontend;
- [x] targeted backend tests и frontend build пройдены.
