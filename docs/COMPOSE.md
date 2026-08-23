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

Миграция не выполняется автоматически при старте backend. После проверки
конфигурации базы применить baseline явно:

```powershell
docker compose --profile migrate run --rm migrate
```

Это изменяет только локальный PostgreSQL volume Compose. Для остановки:

```powershell
docker compose down
```

Для удаления локальных данных PostgreSQL/Redis нужна отдельная явная команда:

```powershell
docker compose down -v
```

Она необратимо удалит volumes этого Compose-проекта.
