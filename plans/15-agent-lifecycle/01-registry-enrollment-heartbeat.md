# 15. Station registry, enrollment и heartbeat

## Цель

Закрыть следующий read-only backend slice: оператор создаёт draft station,
агент одноразово enroll-ится, а затем отправляет heartbeat с process/drive
snapshot. Эти операции меняют только PostgreSQL read-model и не выполняют
TrueNAS actions.

## Изменяемые модели

- `enrollment_tokens`: hash, station binding, expiry, used/revoked timestamps;
- `process_snapshots`: normalized processes/drives, marker, capture/receive time;
- `agents`: credential hash, enrollment metadata и heartbeat timestamps;
- station operational state обновляется до `online` только после валидного
  heartbeat для enabled station.

## API routes

- `POST /api/v1/stations` — Basic Auth, создать station draft и вернуть token
  один раз;
- `POST /api/v1/agents/enroll` — token auth, атомарно claim token и выдать
  ограниченный agent credential;
- `POST /api/v1/agents/heartbeat` — Bearer agent credential, проверить binding,
  timestamp и записать snapshot;
- существующие `GET /health` и `GET /api/v1/stations` не менять по контракту.

## Migration plan

1. Расширить `Base.metadata` таблицами enrollment/snapshot.
2. Alembic revision для изменений только сгенерировать отдельной явной командой
   после review metadata.
3. В этой итерации revision не применять и реальную БД не подключать.

## Ключевые тесты

- station create возвращает token, в БД лежит только hash;
- повторный/просроченный/revoked token отклоняется;
- enroll атомарно помечает token used и создаёт agent;
- credential не возвращается из read model и неверный Bearer получает `401`;
- heartbeat проверяет station binding, revoked/disabled state и timestamp skew;
- валидный heartbeat сохраняет process/drive snapshot и обновляет freshness;
- duplicate agent UUID/station binding отклоняется constraint-ом.

## Запреты

- не хранить plaintext enrollment token или agent credential;
- не выполнять shell/process termination на сервере;
- не подключать реальный Windows agent, PostgreSQL или TrueNAS;
- не добавлять TrueNAS API key в request/response;
- не применять Alembic revision автоматически.

## Критерий завершения

Application use cases работают через Protocol/UoW, API contract tests проходят на
SQLite/fake boundary, секреты redacted/hashed, а `STATE.md` фиксирует следующий
шаг — process rules/preflight.

## Статус

- [x] domain/application lifecycle models созданы;
- [x] persistence repositories и metadata созданы;
- [x] registry/enrollment/heartbeat routes созданы;
- [x] ключевые lifecycle/security tests созданы;
- [x] проверки выполнены;
- [x] `STATE.md` обновлён.

Подшаг завершён. Реальный agent/PostgreSQL/NAS не подключались; следующий
подшаг — process rules и preflight core.
