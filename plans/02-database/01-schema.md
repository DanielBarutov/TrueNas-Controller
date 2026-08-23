# 02. Схема данных

## Цель

Хранить состояние станций и публикаций так, чтобы повторный запуск был безопасным, audit был воспроизводимым, а старый mapping оставался доступным до verify.

## Основные таблицы

### `stations`

- `id UUID PK` — внутренний идентификатор;
- `station_id UUID UNIQUE` — стабильный идентификатор enrollment/агента;
- `display_name`, `hostname`;
- `role` — `admin | client`;
- `enabled`, `deleted_at`;
- `tags JSONB` или нормализованная связь tags;
- `current_version_id`, `desired_version_id`;
- `state`, `state_reason`;
- `target_name`, `target_iqn`, `initiator_iqn`;
- `created_at`, `updated_at`.

IP и MAC не являются primary key. Историю наблюдений хранить отдельно или в ограниченном snapshot record.

### `agents`

- `id UUID PK`, `station_id FK UNIQUE`;
- `agent_uuid`, `agent_version`;
- `credential_hash`, `credential_created_at`, `revoked_at`;
- `last_seen_at`, `last_heartbeat_at`, `last_process_snapshot_at`, `last_drive_snapshot_at`;
- `last_ip_addresses JSONB`, `last_mac_addresses JSONB`;
- `status`, `last_error`.

Секрет агента хранить только в виде проверяемого хеша, если протокол это допускает. Одноразовый enrollment token не хранить в открытом виде.

### `process_snapshots`

- `id UUID PK`, `station_id FK`, `captured_at`, `received_at`;
- `processes JSONB` — нормализованные name/pid/path;
- `drives JSONB` — letter/present/free_bytes;
- `game_version_marker`;
- `agent_version`;
- `freshness_status`.

Retention ограничить, например последние N snapshot на станцию или короткое время. Audit не удалять вместе с оперативным snapshot.

### `process_rules`

- `id UUID PK`;
- `name`, `role`;
- `required_closed`, `severity`;
- `enabled`, `persistent_policy`;
- `tag_selector`;
- `created_by`, `updated_at`.

Правила редактируемые; default rules — seed/конфигурация, а не зашитые проверки в workflow.

### `storage_versions`

- `id UUID PK`, `job_id FK nullable`;
- `label UNIQUE`, `kind` (`master_snapshot | client_clone`);
- `parent_version_id`;
- `station_id nullable` — master не привязан к станции, clone привязан;
- `truenas_object_ref JSONB` — opaque IDs/path, не UI input;
- `status` (`created | staged | active | superseded | failed | retained`);
- `created_at`, `verified_at`.

Нельзя помечать старую версию `superseded` до успешной verify новой для станции.

### `publish_jobs`

- `id UUID PK`, `idempotency_key UNIQUE`;
- `label`, `description`, `game_name`;
- `dry_run DEFAULT true`;
- `allow_hot_switch DEFAULT false`;
- `step`, `status`, `status_reason`;
- `operator_id`, `created_at`, `started_at`, `completed_at`;
- `master_version_id nullable`;
- `client_confirmation` и `client_confirmation_at`;
- `correlation_id`.

### `publish_targets`

- `id UUID PK`, `job_id FK`, `station_id FK`;
- `selected_at`, `deselected_at`;
- `preflight_status`, `preflight_result JSONB`;
- `old_version_id`, `new_version_id`;
- `old_mapping JSONB`, `new_mapping JSONB`;
- `switch_status`, `verify_status`, `error_code`, `error_message`;
- `progress_percent`, `updated_at`.

Уникальность `(job_id, station_id)`. Нельзя включать disabled/deleted station в apply без нового явного выбора и preflight.

### `audit_events`

- `id BIGSERIAL/UUID PK`;
- `occurred_at`, `operator_id`, `job_id`, `station_id`, `correlation_id`;
- `event_type`, `severity`;
- `old_state`, `new_state`;
- `payload JSONB` без секретов;
- `error_code`, `message`.

Audit append-only. Исправление ошибки — новое событие, не переписывание старого.

### Вспомогательные таблицы

- `enrollment_tokens`: hash, station draft/reference, expires_at, used_at, revoked_at;
- `agent_commands`: refresh command, status, created_at, acknowledged_at, expires_at;
- `operator_sessions` или внешний identity mapping — в зависимости от выбранной auth-модели;
- `outbox_events`: если publish progress должен надёжно доставляться после commit БД.

## Связи

```text
station 1──1 agent
station 1──N process_snapshot
station 1──N publish_target
publish_job 1──N publish_target
publish_job 1──N storage_version
publish_job 1──N audit_event
storage_version 1──N storage_version (parent/clone)
```

## Транзакционные правила

1. Создание job и его target rows — одна транзакция.
2. Переход job и запись audit — одна транзакция.
3. Публикация outbox event — в той же транзакции, что и изменение состояния.
4. Перед switch брать advisory lock на job и station set.
5. Перед применением перечитать station, target и mapping из БД.
6. Ошибка adapter фиксируется на target и job; старый mapping сохраняется.

## Миграции и SQLite

Основная схема ориентирована на PostgreSQL: UUID, JSONB, advisory lock и конкурентные ограничения. Для локального SQLite допускается совместимый repository/test profile, но SQLAlchemy models и application boundary не должны зависеть от конкретного драйвера. Различия lock/JSON покрыть отдельными integration tests.

## Индексы и ограничения

- `stations(enabled, state)`;
- `agents(last_seen_at)`;
- `process_snapshots(station_id, captured_at DESC)`;
- `publish_targets(job_id, switch_status)`;
- `audit_events(job_id, occurred_at)`;
- unique active target mapping per station;
- unique `storage_versions(label)`;
- CHECK для role/status enums на уровне domain и, где удобно, БД.

## Необратимые операции

В схеме нет автоматического hard delete storage. Cleanup и destroy должны быть отдельным будущим use case с retention policy, dry-run, подтверждением и audit.
