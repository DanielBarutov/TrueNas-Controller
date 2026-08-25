# План 37. Реестр dataset и cleanup worker

## Цель

Сохранять созданные в ходе live publish dataset/clone с job, station,
snapshot, timestamp и признаком текущего mapping. Запускать периодический
cleanup worker с настраиваемым интервалом и retention.

## Безопасная политика

- новые dataset регистрируются до возможности cleanup;
- текущий dataset станции не является кандидатом на удаление;
- по умолчанию cleanup только формирует кандидатов и не выполняет destroy;
- фактическое удаление включается отдельным `TRUENAS_CLEANUP_APPLY_ENABLED`;
- default interval — 7 дней, retention и batch size задаются env.

## Чекап

- [x] persistence model/repository/migration и job details добавлены;
- [x] TrueNAS delete adapter остаётся allowlisted и fail-closed;
- [x] Dramatiq cleanup actor запускается по настраиваемому расписанию;
- [x] тесты подтверждают dry-run cleanup, bounded failure и отдельный apply gate;
- [ ] применить migration и сделать Compose dry-run на пользовательском окружении.
