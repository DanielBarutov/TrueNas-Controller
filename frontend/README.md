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

Пароль Basic Auth вводится на login-экране и хранится только в памяти вкладки.
Frontend не содержит TrueNAS API key, agent credential или private signing key.

Первый срез включает overview, station list/create и встроенную Markdown-базу
знаний. Полный preflight/publish workflow будет подключаться следующими
подшагами плана 31.
