# 04. Безопасность и отказоустойчивость

## Цель

Снизить риск случайного переключения активной игры, утечки TrueNAS credentials и разрушения старой рабочей версии.

## Угрозы

| Угроза | Защита | Проверка |
|---|---|---|
| API key попал во frontend | secret только API/worker, frontend получает лишь статус | поиск секретных имён в bundle/logs |
| украден enrollment token | одноразовый, TTL, hash, revoke после регистрации | unit + integration tests |
| поддельный heartbeat | отдельный agent credential, station binding, timestamp/freshness | invalid credential/station tests |
| повтор switch | idempotency key, DB/advisory lock, read-back | replay tests |
| switch активной игры | required_closed, idle policy, explicit confirmation | blocking preflight tests |
| stale snapshot выглядит зелёным | freshness calculated server-side и видимая причина | clock/age tests |
| один LUN подключён к двум ПК | mapping validation и unique active binding | invariant test |
| worker retry ломает состояние | timeout, unknown state, read-back, compensation | fault injection |
| оператор удалил старую версию | cleanup отдельный, dry-run, retention, confirmation | negative tests |
| TrueNAS API наружу | adapter только backend network, bind LAN/localhost | Compose/config review |

## Секреты

- TrueNAS API key: Docker secret или environment secret backend/worker; не хранить в БД в открытом виде.
- Agent credential: отдельный ограниченный credential на агента; отзыв и ротация.
- Enrollment token: одноразовый, короткий TTL, в БД только hash.
- Frontend config: только публичный API base URL и feature status, без секретов.
- Logs: redact authorization headers, tokens, API key, raw credentials и полные payload с секретами.

## Enrollment protocol

1. Оператор создаёт draft station и одноразовый token.
2. UI показывает token/команду установки один раз; token имеет TTL.
3. Агент отправляет token, station metadata и свой generated agent UUID по HTTPS.
4. Backend атомарно проверяет token, связывает agent со station и помечает token used.
5. Backend выдаёт ограниченный credential; повторное использование token отклоняется.
6. Агент сохраняет credential локально с ACL службы.
7. Re-enrollment отзывает старый credential и пишет audit.

## Auth и права

Для собственного API/UI выбран **HTTP Basic Auth** с пользователем `admin`. Пароль передаётся через `BASIC_AUTH_PASSWORD`, не записывается в планы, git, frontend bundle или логи. Basic Auth разрешён только поверх HTTPS; при отключённой TLS-проверке UI обязан показывать warning.

Даже локальный MVP должен иметь явную boundary: кто может редактировать stations/rules, запускать publish, разрешать hot switch и cleanup. Cleanup и hot switch — отдельные permissions/confirmation. Basic Auth приложения не заменяет TrueNAS API key: TrueNAS credential остаётся только backend/worker secret.

## Сетевые границы

- Агент инициирует исходящее соединение к API.
- API/worker инициируют соединения к TrueNAS.
- TrueNAS API не проксируется через browser.
- Compose bind по умолчанию — localhost или доверенный LAN interface.
- TLS verification включена. Отключение — отдельный локальный флаг, warning в UI и audit event.

## Audit policy

Записывать: actor, время, job/station, старый/новый version, target/extent opaque IDs, confirmation text/result, dry-run, hot-switch flag, adapter method category, error and correlation ID. Не записывать API key, enrollment token, agent credential и лишние персональные данные.

## Backup и восстановление

- Резервировать PostgreSQL и конфигурацию правил/политик.
- Перед восстановлением сверить audit и фактический target mapping через read-only adapter.
- При расхождении БД и NAS не выполнять switch/cleanup автоматически.
- Сначала создать incident/audit record, затем вручную определить authoritative state.

## Error handling

Ошибки разделять на validation, auth, stale, conflict/busy, adapter timeout, adapter rejected, unknown state и internal. UI показывает оператору безопасное сообщение и correlation ID; подробности доступны в серверном audit/log, без секретов.
