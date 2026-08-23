# Запуск backend на Windows

## PowerShell

В корне проекта выполни:

```powershell
Set-Location C:\path\to\tnas
$env:BASIC_AUTH_PASSWORD = "<пароль-оператора>"
$env:DATABASE_URL = "sqlite+aiosqlite:///./local.db"
uv run alembic upgrade head
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

Открой `http://127.0.0.1:8000/docs`. Для доступа с другого ПК используй IP
админского компьютера и разреши входящий TCP-порт 8000 в Windows Firewall.

Логин собственного API — `admin`. Пароль задаётся только переменной
`BASIC_AUTH_PASSWORD`; его нельзя хранить в frontend, Markdown, git или логах.

## База данных

Текущий локальный профиль использует SQLite `local.db`, поэтому отдельный
пароль базы данных не нужен. PostgreSQL и Redis Compose-профиль будут добавлены
отдельным deployment-планом. Для production не использовать SQLite.

`213.108.6.24/api/docs` — это документация TrueNAS, а не адрес Controller API.
Frontend обращается к собственному backend через `/api`.
