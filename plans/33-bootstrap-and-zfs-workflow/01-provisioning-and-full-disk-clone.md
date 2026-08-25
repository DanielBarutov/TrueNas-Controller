# 33. Автоматический onboarding и публикация полного диска

## Цель

Убрать ручное создание station на каждом клиентском ПК и привести publish-модель
к фактической операции: snapshot исходного TrueNAS dataset и clone в новый
dataset для выбранной клиентской станции.

## Принятые решения

- Оператор в UI получает отдельный одноразовый `provisioning token` с коротким
  TTL через Basic Auth.
- Клиентский exe не получает Basic Auth `admin`, пароль приложения или пароль
  Windows. Token вводится видимо в консоли и не сохраняется в argv.
- `POST /api/v1/agents/bootstrap` атомарно потребляет token, создаёт или
  восстанавливает client station по UUID из `station-report.json` и создаёт
  agent credential.
- Существующий credential сначала проверяется heartbeat-запросом; наличие файла
  само по себе больше не пропускает enrollment.
- Admin station не является обязательной станцией workflow. Controller UI —
  операторский control plane, а client stations — потребители clone. Секция
  admin preflight оставлена опциональной для совместимости.
- Источник publish называется `source_dataset`, например
  `games/master-games`; понятие отдельной игры и `game_version_marker` не входит
  в этот workflow.

## TrueNAS workflow

1. Read-check исходного dataset `games/master-games` и отсутствие конфликтующего
   target dataset.
2. В dry-run построить план действий без изменения NAS.
3. В apply создать snapshot исходного dataset через `pool.snapshot.create`.
4. Read-back snapshot и передать полное имя snapshot в `pool.snapshot.clone`.
5. Создать новый dataset для конкретной станции, например
   `games/master-games-v002-clone-pc1`.
6. Отдельно проверить mapping/target/extent и heartbeat client station.

Нельзя автоматически удалять старые snapshots, datasets, clones, mappings или
откатывать успешные станции. Конфликт существующего target требует явного
решения оператора. Реальный apply остаётся отдельным opt-in gate.

## Реализовано в текущем срезе

- domain/application/repository/UoW для provisioning tokens;
- migration `7f5d0f1c9b42` для token table;
- `POST /api/v1/provisioning-tokens` с Basic Auth;
- `POST /api/v1/agents/bootstrap` без Basic Auth;
- native .NET installer: default visible provisioning prompt,
  `--provisioning-token`, manual `--enrollment-token` fallback;
- UI-кнопка выпуска token;
- optional admin station в publish preflight;
- `game_name` → `source_dataset` в актуальном ORM/API/frontend contract и
  migration `8a9c2d7e4f11`.

## Следующий срез

- добавить write-capable TrueNAS adapter только за explicit apply gate;
- описать точные JSON-RPC params и idempotency keys для snapshot/clone;
- заменить fake master/clone executor на storage plan/result с dataset paths;
- добавить acceptance на fake TrueNAS adapter и read-back конфликтов;
- выполнить отдельный согласованный LAN smoke только для read-only методов.

## Проверки

- backend key/full tests;
- frontend tests и production build;
- Ruff;
- Alembic upgrade head на изолированной SQLite/PostgreSQL базе;
- native .NET self-contained publish и checksum;
- Windows client smoke остаётся внешней проверкой на клиентском ПК.

## Запреты

- не выполнять реальные `pool.snapshot.create`, `pool.snapshot.clone` или
  mapping switch без отдельного apply-разрешения;
- не отправлять Basic Auth и TrueNAS credentials в native exe;
- не делать station/admin PC обязательным условием для полного-disk clone.
