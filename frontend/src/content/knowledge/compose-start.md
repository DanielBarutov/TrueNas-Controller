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

Backend автоматически выполняет `alembic upgrade head` перед запуском API.
Если миграция не проходит, контейнер backend завершится с ошибкой, а причина
останется в логах:

```powershell
docker compose logs backend
```

Если видишь `Can't locate revision identified by 'head'`, проверь наличие
файла `repository/migrations/versions/bee81bac70cc_initial_schema.py` в
checkout. Строка shell entrypoint должна оставаться именно
`set -Eeuo pipefail`; вариант `set eeuo pipfail` неверен. Backend не должен
запускаться после неудачной миграции.

После исправления `.env` или изменения схемы пересобери backend:

```powershell
docker compose up -d --build backend frontend
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

Ошибка `set: invalid option name` в начале логов backend означает, что shell
entrypoint пришёл в Linux-контейнер с Windows-окончаниями строк. Обнови проект
и пересобери backend после исправления:

```powershell
git pull --ff-only origin main
docker compose build --no-cache backend
docker compose up -d postgres redis backend
```
