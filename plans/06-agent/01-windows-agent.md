# 06. Windows-агент

## Цель

Небольшая служба наблюдения на админском и игровых ПК, которая сообщает состояние и выполняет только безопасную локальную команду refresh.

## Компоненты агента

- `agent.py` — lifecycle, reconnect, heartbeat scheduler;
- `process_monitor.py` — `psutil.process_iter()` и нормализация;
- `drive_monitor.py` — доступность `D:` и free bytes;
- `enrollment.py` — initial registration и credential storage;
- `windows_service.py` — service wrapper, stop/start, graceful shutdown;
- `protocol.py` — versioned payload and server command validation;
- `config.py` — API URL, station UUID, credential path, interval.

## Быстрый отчёт для onboarding клиента

До полноценной установки службы клиентский ПК может запустить
[`scripts/agent_station_report.py`](../../scripts/agent_station_report.py).
Скрипт использует только стандартную библиотеку Python и возвращает JSON с:

- `station.display_name`, `station.hostname`, `station.role` — данными для
  создания station;
- стабильным `agent.agent_uuid`, версией агента и hostname;
- справочными IP/MAC и состоянием `D:`.

Пароли, Basic Auth, enrollment token и credential в отчёт не входят. UUID
сохраняется в `%LOCALAPPDATA%\TrueNasController\agent\identity.json` на
Windows и переиспользуется при повторном запуске. Оператор вставляет JSON в
frontend, создаёт station и отдельно передаёт клиенту одноразовый token.
Полный enrollment и установка службы по-прежнему выполняются по
[`docs/AGENT_INSTALL.md`](../../docs/AGENT_INSTALL.md).

## Heartbeat

Период 5–15 секунд с configurable jitter. Payload:

- station ID, hostname, agent version, timestamp;
- IP/MAC как справочные признаки;
- process snapshot timestamp и процессы `name/pid/path`;
- drive `letter/present/free_bytes`;
- optional diagnostic code, но без файлов, содержимого игр и секретов.

Backend считается authoritative для freshness: агент не может сам заявить `healthy` и тем самым снять stale.

## Process monitor

Использовать `psutil.process_iter()` с безопасной обработкой `AccessDenied`, `NoSuchProcess`, `ZombieProcess` и неожиданного отсутствия атрибута. Нормализовать имя процесса и сохранять PID/path, если доступны. Не завершать процессы. Не считать `vgc.exe` blocking автоматически — это определяется правилом/persistent policy.

## Drive

- Проверить `D:` exists/present.
- Получить free bytes без чтения пользовательских файлов.
- Ошибка доступа к `D:` — blocking или unknown по политике, но не зелёный результат.

Факт обновления игры не проверяется агентом. Оператор подтверждает его отдельно;
это не является preflight/verify gate и не требует game-specific настройки.

## Reconnect и offline

При network failure агент делает bounded exponential backoff с jitter. Не спамит лог и не меняет локальные данные destructive образом. После восстановления отправляет новый snapshot. Offline/stale вычисляет backend по last_seen.

## Server refresh

Поддержать только команду `refresh_process_snapshot` с command ID, expiry и signature/auth context. Агент выполняет локальный сбор и отправляет heartbeat. Любая неизвестная команда отклоняется и логируется. Shell, PowerShell и arbitrary process launch не входят в MVP.

## Service deployment

Установщик должен:

1. установить бинарный/packaged агент;
2. создать конфигурацию с API URL и station ID;
3. сохранить credential с ACL службы;
4. зарегистрировать Windows Service через выбранный wrapper;
5. предоставить uninstall/re-enrollment инструкцию;
6. не требовать TrueNAS credentials.

Отдельно проверить запуск от обычной учётной записи; SYSTEM не использовать без доказанной необходимости.

## Agent tests

- process iterator: normal, AccessDenied, process исчез между итерациями;
- drive present/missing/low space;
- payload schema and redaction;
- enrollment one-shot, expired token, wrong station;
- reconnect/backoff;
- unknown command rejection;
- service lifecycle через mock wrapper;
- compatibility test для разных agent versions.

## Текущий прогресс реализации

- [x] process collector на `psutil.process_iter()` с нормализацией и безопасным
  пропуском недоступных/исчезнувших процессов;
- [x] drive collector для `D:` с present/free bytes и fail-closed missing/denied
  результатом;
- [x] snapshot composer с UTC timestamp, station ID и agent version;
- [x] ключевые collector tests: normal, denied/disappeared process и drive
  missing/invalid letter;
- [x] versioned heartbeat payload и HTTPS transport с Bearer credential,
  TLS-only default и redacted status errors;
- [x] bounded exponential backoff с jitter и retry contract tests;
- [x] command validator принимает только подписанный unexpired
  `refresh_process_snapshot`, без shell/PowerShell execution;
- [x] heartbeat HTTP client transport и reconnect/backoff boundary;
- [x] scheduler wiring через `AgentService`, command handler и local refresh
  execution boundary;
- [x] one-shot enrollment coordinator и atomic file credential-store fallback;
- [x] server heartbeat contract `protocol_version=1` с валидацией и сохранением
  hostname/IP/MAC metadata в station/agent binding;
- [x] `CredentialProtector` через `Protocol`, atomic protected-byte store и
  Windows DPAPI adapter с user-scope по умолчанию; plaintext store остаётся
  только явным development fallback;
- [x] потокобезопасный `WindowsServiceHost` и pywin32 SCM wrapper с graceful
  stop; pywin32 подключается только на Windows;
- [x] Windows ACL adapter применяется к временно записываемому credential blob
  до `os.replace`; platform factory требует явного plaintext fallback только
  вне Windows для development;
- [x] server command issuance, Ed25519 signature transport, heartbeat lease,
  local dedupe и acknowledgement boundary;
- [x] public-key config и agent runtime composition с `Ed25519CommandVerifier`;
- [x] agent entrypoint с explicit one-shot `enroll`, deferred protected
  credential loading при SCM-командах и SCM runtime composition; deployment
  notes вынесены в
  [`docs/AGENT_DEPLOYMENT.md`](../../docs/AGENT_DEPLOYMENT.md);
- [x] baseline Alembic migration сгенерирована, но не применена;
- [x] безопасный stdlib-only station report для первичного onboarding клиента;
- [ ] production installer/service registration и проверка ACL под фактической
  service account;
