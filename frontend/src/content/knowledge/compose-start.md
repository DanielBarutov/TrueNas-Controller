# Запуск всего локального контура через Docker Compose

Compose удобен, когда нужно поднять PostgreSQL, Redis, backend и frontend одной
командой. TrueNAS и Windows-агенты в этот локальный профиль не подключаются.

## PowerShell

В корне проекта:

```powershell
Copy-Item .env.example .env
notepad .env
docker compose up -d --build postgres redis backend frontend
```

В `.env` задай собственные `BASIC_AUTH_PASSWORD` и `POSTGRES_PASSWORD`. В UI
вход выполняется с логином `admin` и значением `BASIC_AUTH_PASSWORD`.

Открой `http://127.0.0.1:5173`. Backend docs доступны на
`http://127.0.0.1:8000/docs`.

## Миграция базы

Миграции не запускаются автоматически. После проверки локального PostgreSQL:

```powershell
docker compose --profile migrate run --rm migrate
```

Остановить сервисы:

```powershell
docker compose down
```

Не выполняй `docker compose down -v`, если нужно сохранить локальные данные.
Эта команда удаляет volumes проекта.

## Диагностика

```powershell
docker compose ps
docker compose logs backend
docker compose logs frontend
```

Если frontend не открывается, сначала дождись статуса `healthy` у backend.
Frontend proxy внутри Compose обращается к сервису `backend`, а при обычном
локальном `npm run dev` использует `127.0.0.1:8000`.
