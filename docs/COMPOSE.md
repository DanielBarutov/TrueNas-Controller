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

Для остановки:

```powershell
docker compose down
```

Для удаления локальных данных PostgreSQL/Redis нужна отдельная явная команда:

```powershell
docker compose down -v
```

Она необратимо удалит volumes этого Compose-проекта.
