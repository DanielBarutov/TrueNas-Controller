# Локальный запуск через Docker Compose

Compose поднимает PostgreSQL, Redis, backend и frontend. Реальные TrueNAS,
Windows-агенты и storage switch в этот профиль не подключаются.

## Первый запуск в PowerShell

Из корня проекта:

```powershell
Copy-Item .env.example .env
notepad .env
docker compose up -d --build postgres redis backend frontend
```

В `.env` обязательно замените оба значения. Откройте:

- frontend: `http://127.0.0.1:5173`;
- backend docs: `http://127.0.0.1:8000/docs`;
- PostgreSQL: `127.0.0.1:5432`;
- Redis: `127.0.0.1:6379`.

Basic Auth использует логин `admin` и значение `BASIC_AUTH_PASSWORD` из `.env`.
Пароль из репозитория не подставляется и не должен попадать в git.

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
