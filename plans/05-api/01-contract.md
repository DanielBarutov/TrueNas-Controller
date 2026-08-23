# 05. API-контракты

## Цель

Дать frontend и агенту стабильный собственный API, скрывающий storage details и вынуждающий backend повторно проверять каждую опасную команду.

## Общие правила

- Prefix: `/api/v1`.
- Операторская auth boundary: HTTP Basic Auth; username `admin`, password из `BASIC_AUTH_PASSWORD`.
- Basic Auth используется только по HTTPS; credential не возвращается API и не пишется в audit/logs.
- Все даты — UTC ISO 8601.
- UUID — строка canonical format.
- Ошибка: `{code, message, correlation_id, details?}` без секретов.
- Команды, изменяющие состояние, принимают `idempotency_key`.
- Browser никогда не получает TrueNAS API key и не вызывает `/api/docs/` TrueNAS.
- `station_ids` из browser — только предложение; backend загружает и проверяет их заново.

## Agent endpoints

### `POST /agents/enroll`

Request: одноразовый token, agent UUID, hostname, agent version, observed IP/MAC. Response: station ID, ограниченный credential/config и server time. Повтор использованного token — конфликт.

### `POST /agents/heartbeat`

Auth agent credential. Payload содержит station ID, timestamp, process snapshot, drives, marker и version. Backend проверяет station binding, размер/формат payload, timestamp skew, нормализует процессы и записывает freshness.

### `POST /agents/{id}/processes/refresh`

Только operator/application service. Создаёт короткоживущую refresh command. Не должен выполнять arbitrary shell/command.

### `GET /agents/{id}/commands`

Если используется polling вместо WebSocket: агент получает только разрешённые типы команд, expiry и command ID.

## Station endpoints

- `GET /stations` — фильтры role/enabled/state/tag, freshness и last error.
- `POST /stations` — создать draft station и, по явному запросу, enrollment token.
- `PATCH /stations/{id}` — display name, role, tags, enabled, mapping metadata; изменения критичных mapping полей требуют audit и повторного preflight.
- `DELETE /stations/{id}` — soft delete/disable по умолчанию.
- `GET /stations/{id}/processes` — последний snapshot и age.
- `GET /stations/{id}/history` — ограниченная история состояний/audit.

## Rule endpoints

Нужны `GET/POST/PATCH/DELETE /process-rules`. Изменение enabled/required_closed/severity не меняет старые audit results, но влияет на новый preflight.

## Preflight endpoints

- `POST /preflight/admin` — запросить свежий snapshot и вычислить admin result.
- `POST /publish/jobs/{id}/preflight` — проверить выбранные targets и вернуть per-station results.
- `POST /publish/jobs/{id}/confirm` — принять `confirmation=true/false`, actor, optional note; всегда audit.

## Publish endpoints

- `POST /publish/jobs` — создать draft, `dry_run=true` по умолчанию.
- `GET /publish/jobs/{id}` — job, target results, step, errors, links to audit.
- `POST /publish/jobs/{id}/switch` — station IDs, idempotency key, dry-run/hot-switch flags; backend повторно проверяет all preconditions.
- `POST /publish/jobs/{id}/rollback` — одна station за запрос или явно ограниченный список; старый mapping берётся из trusted DB state и read-back.
- `POST /publish/jobs/{id}/cleanup` — только dry-run по умолчанию, retention policy и отдельное подтверждение.
- `WS /publish/jobs/{id}/events` — прогресс и переходы без секретных payload.

## События

Типы: `job.created`, `job.step_changed`, `target.preflight_updated`, `target.switch_started`, `target.switch_progress`, `target.switch_finished`, `target.verify_finished`, `job.warning`, `job.completed`, `job.partial_failure`, `job.recovery_required`.

Каждое событие содержит `event_id`, `occurred_at`, `job_id`, optional `station_id`, `status`, `progress`, `correlation_id` и safe `message`.

## HTTP semantics

- `400` invalid input;
- `401/403` auth/permission;
- `404` unknown resource;
- `409` stale/busy/conflicting state or reused idempotency key with different body;
- `422` domain precondition failure with per-target details;
- `503` dependency unavailable;
- `500` internal error with correlation ID only.

## WebSocket policy

WebSocket events — только server → browser для progress. Reconnect должен позволить получить current job snapshot и не считать пропущенное событие потерей состояния. Источник истины — БД, не Redis stream alone.
