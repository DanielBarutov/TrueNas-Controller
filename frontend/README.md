# TrueNAS Controller frontend

## Локальный запуск на Windows PowerShell

Сначала запусти backend на `http://127.0.0.1:8000`, затем:

```powershell
Set-Location C:\path\to\tnas\frontend
npm install
npm run dev
```

Открой `http://127.0.0.1:5173`. Vite proxy передаёт `/health` и `/api` на
`http://127.0.0.1:8000`, поэтому отдельная CORS-настройка для локальной
разработки не нужна.

Production build:

```powershell
npm run build
npm run preview
```

Ключевые frontend-проверки:

```powershell
npm run test
```

Пароль Basic Auth вводится на login-экране и хранится только в памяти вкладки.
Frontend не содержит TrueNAS API key, agent credential или private signing key.

Срез включает overview, station list/create, publish wizard и встроенную
Markdown-базу знаний. Frontend не выполняет storage-операции и не проверяет
версию игры: это подтверждает оператор, а backend остаётся источником истины.
