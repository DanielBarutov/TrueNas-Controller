# План 39. Live-сверка dataset mapping и отдельный cleanup apply

## Цель

Считать текущей ту tracked-версию, которая фактически подключена к iSCSI
target станции в TrueNAS, а не ту, на которой остался флаг в базе Controller.
Разрешить удаление выбранных неиспользуемых версий из UI без включения
полноценного publish/switch режима.

## Входы и зависимости

- `Station.target_name` и tracked `publish_artifacts`;
- read-only TrueNAS JSON-RPC методы target, extent и targetextent;
- существующий API → Redis/Dramatiq worker cleanup flow;
- отдельные `TRUENAS_APPLY_ENABLED` и `TRUENAS_CLEANUP_APPLY_ENABLED`.

## Решения и инварианты

- Перед выдачей списка и постановкой удаления Controller сверяет live-цепочку
  `station.target_name → target → extent → extent.path`.
- Если live mapping совпал ровно с одной tracked-версией, она становится
  `current`, а предыдущий DB-флаг синхронизируется в `retired`.
- Если mapping отсутствует, неоднозначен или указывает на нетрекнутую версию,
  UI не получает ложный current, а cleanup выбранной станции отклоняется.
- Чтение TrueNAS выполняется backend read-only client; секрет не попадает во
  frontend и API-ответ.
- `TRUENAS_CLEANUP_APPLY_ENABLED=true` включает только удаление dataset через
  cleanup worker. Publish остаётся fake, пока отдельно не включены
  `PUBLISH_EXECUTOR_MODE=truenas` и `TRUENAS_APPLY_ENABLED=true`.
- Периодический retention scheduler по умолчанию выключен; удаление доступно
  через checkbox-меню.

## Изменения

- application/repository: live reconciliation и persisted current state;
- API composition: read-only TrueNAS client для dataset inventory;
- worker runtime: независимый cleanup write gate;
- Compose, `.env.example` и документация;
- tests: manual mapping switch, untracked mapping, repository sync и fake
  publish + real cleanup configuration.

## Проверки и результат

- [x] focused dataset/repository/worker tests;
- [x] полный backend pytest suite;
- [x] Ruff check/format и compileall;
- [x] `docker compose config`;
- [x] фактический TrueNAS delete не запускался.

## Статус

Локальный implementation slice завершён. Реальный cleanup запускается только
после перезапуска worker с текущим `.env`; live TrueNAS smoke и удаление dataset
в рамках разработки не выполнялись.
