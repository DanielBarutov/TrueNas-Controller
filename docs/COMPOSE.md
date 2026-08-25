# Локальный запуск через Docker Compose

Compose поднимает PostgreSQL, Redis, backend, publish worker и frontend.
По умолчанию worker запускает детерминированный fake executor. Реальный TrueNAS
подключается только при явном `PUBLISH_EXECUTOR_MODE=truenas` и отдельном
`TRUENAS_APPLY_ENABLED=true`.

## Первый запуск в PowerShell

Из корня проекта:

```powershell
Copy-Item .env.example .env
notepad .env
docker compose up -d --build postgres redis backend worker frontend
```

В `.env` обязательно замените оба значения. Откройте:

- frontend: `http://127.0.0.1:5173`;
- backend docs: `http://127.0.0.1:8000/docs`;
- PostgreSQL: `127.0.0.1:5432`;
- Redis: `127.0.0.1:6379`.

Проверить очередь и outbox можно так:

```powershell
docker compose ps
docker compose logs --tail=100 worker
```

После dispatch в логах worker должен появиться `outbox poll` с
`dispatched=1`. Если job была создана в `dry_run=true`, она завершится как
`simulated`; это не означает, что TrueNAS был изменён.

Basic Auth использует логин `admin` и значение `BASIC_AUTH_PASSWORD` из `.env`.
Пароль из репозитория не подставляется и не должен попадать в git.

`TRUENAS_API_KEY` — отдельный ключ TrueNAS, не Basic Auth приложения. Для
подключения worker нужны `TRUENAS_VERSION`, полный `TRUENAS_WS_URL`,
`TRUENAS_API_KEY` и `PUBLISH_EXECUTOR_MODE=truenas`. Запись на NAS дополнительно
останется выключенной, пока явно не задано `TRUENAS_APPLY_ENABLED=true`.

Даже в режиме `truenas` dry-run не выполняет snapshot, clone или update extent:
он только читает dataset, target/extent association и строит ожидаемый zvol.
Первый apply следует выполнять на одной выделенной станции и проверять
read-back существующего extent.

## Read-only smoke конкретного TrueNAS

Для первого подключения не переводите Compose worker в write-профиль. В
PowerShell из корня проекта задайте параметры только в текущем процессе и
запустите opt-in integration test:

```powershell
$env:TRUENAS_VERSION = "25.10.5"
$env:TRUENAS_WS_URL = "ws://<nas-host>/api/current"
$env:TRUENAS_API_KEY = "<вставьте-ключ-только-локально>"
$env:RUN_TRUENAS_SMOKE = "1"
uv run pytest -q tests/truenas_adapter/test_integration.py
```

Если TrueNAS опубликован через TLS, используйте `wss://`. Адрес
`/api/docs` — это документация, а не WebSocket endpoint; для API нужен
`/api/current`. Тест выполняет только `core.ping` и чтение datasets,
snapshots, targets, extents и targetextent associations. После проверки ключ
можно убрать из текущей сессии:

```powershell
Remove-Item Env:TRUENAS_API_KEY, Env:RUN_TRUENAS_SMOKE, Env:TRUENAS_WS_URL, Env:TRUENAS_VERSION
```

## Миграции

Backend перед запуском Uvicorn синхронно выполняет `alembic upgrade head`.
Если миграция завершается ошибкой, backend-контейнер останавливается и не
маскирует проблему запуском API. После изменения схемы достаточно пересобрать
backend:

```powershell
docker compose up -d --build backend frontend
docker compose logs backend
```

Ошибка `Can't locate revision identified by 'head'` означает, что в checkout
нет Alembic revision-файла или он не попал в Docker context. Проверьте в
PowerShell:

```powershell
Get-ChildItem .\repository\migrations\versions\*.py
```

В текущем baseline должен присутствовать файл
`bee81bac70cc_initial_schema.py`. Не заменяйте строку entrypoint на
`set eeuo pipfail`: правильный Bash-синтаксис — `set -Eeuo pipefail`. При
ошибке миграции API не должен запускаться.

Если backend завершается с `set: invalid option name` в строке
`backend-entrypoint.sh`, это обычно CRLF из Windows checkout. Репозиторий
фиксирует shell-файлы в LF, а Dockerfile дополнительно нормализует entrypoint
внутри Linux-образа. Обновите checkout и пересоберите backend:

```powershell
git pull --ff-only origin main
docker compose build --no-cache backend
docker compose up -d postgres redis backend
docker compose logs --tail=100 backend
```

Для остановки:

```powershell
docker compose down
```

Для удаления локальных данных PostgreSQL/Redis нужна отдельная явная команда:

```powershell
docker compose down -v
```

Она необратимо удалит volumes этого Compose-проекта.
