# 31. Operator frontend и база знаний

## Цель

Создать отдельный React/Vite/TypeScript frontend для оператора контроллера.
Frontend должен объяснять смысл полей и опасных опций, показывать актуальное
состояние станций и содержать встроенную Markdown-базу знаний с инструкциями
по backend, enrollment и управлению Windows-агентами.

## Входы

- API-контракты из [плана 05](../05-api/01-contract.md);
- read-only stations, enrollment, heartbeat, preflight и publish routes;
- правила безопасности из [плана 04](../04-security/01-security.md);
- инструкции агента из [`docs/AGENT_INSTALL.md`](../../docs/AGENT_INSTALL.md) и
  [`docs/AGENT_DEPLOYMENT.md`](../../docs/AGENT_DEPLOYMENT.md);
- Basic Auth с операторским пользователем `admin`.

## Архитектура frontend

```text
presentation (pages/components/forms)
        ↓
application (API client, query/command orchestration)
        ↓
domain (types, status labels, UI safety rules)
        ↓
infrastructure (fetch, Vite proxy, Markdown content registry)
```

MVP-структура:

```text
frontend/
├── src/
│   ├── application/       # API client и UI use cases
│   ├── domain/            # DTO/types/status presentation rules
│   ├── presentation/      # pages, reusable components, forms
│   │   └── pages/          # publish wizard и экранные композиции
│   └── content/knowledge/ # allowlisted Markdown documents
├── package.json
└── vite.config.ts
```

Frontend не знает TrueNAS URL, API key, agent credential или private signing
key. Basic Auth credential живёт только в памяти текущей вкладки и не
сохраняется в localStorage/cookies в MVP. Vite dev proxy используется для
локальной same-origin разработки.

## Этапы

### 31.01. Каркас и навигация

- React/Vite/TypeScript project;
- shell с navigation: overview, stations, knowledge base;
- login form с объяснением Basic Auth и ошибками 401;
- API client с единым mapping ошибок;
- responsive layout для админского ПК.

### 31.02. Станции и агентские операции

- stations table с hostname, role, status, freshness и agent metadata;
- пояснения к каждому статусу и безопасное различие `offline`/`stale`;
- создание station/enrollment flow с предупреждением о TTL one-shot token;
- вставка JSON station report клиента с автозаполнением station-полей и
  отображением стабильного `agent_uuid`;
- refresh process snapshot command только через backend API;
- отображение последнего heartbeat и объяснение, почему browser не видит
  Windows-процессы напрямую;
- destructive/unsupported controls не рисовать до появления backend route.

### 31.03. Preflight и publish wizard

- admin/client process checks;
- exact blocking process/PID и drive checks;
- multi-select только online/fresh станций;
- явные пояснения `dry_run`, `idle_only`, `allow_hot_switch`, cleanup;
- факт обновления игры подтверждается оператором; UI не запрашивает и не хранит
  game-specific version marker;
- server response остаётся authoritative: UI не может сам разблокировать шаг;
- partial failure, rollback и recovery-required состояния.

Фактически реализованный безопасный срез:

- backend routes prepare и dispatch используют существующие application
  use cases и Basic Auth;
- frontend wizard выполняет draft, server-side preflight, operator
  confirmation и outbox dispatch;
- после dispatch frontend читает GET job read model с polling и показывает
  общий/target progress;
- блокирующие и unknown reports не превращаются в ready на стороне browser;
- dispatch показывает только accepted/persisted state; completed, partial
  failure, failed и recovery_required берутся только из backend read model.

### 31.04. Knowledge base / Markdown reader

- curated registry документов без произвольного чтения файлов из browser;
- Markdown/GFM rendering с заголовками, таблицами, code blocks и links;
- поиск по title/description/content;
- инструкции минимум по разделам:
  - запуск backend на Windows PowerShell и SQLite/PostgreSQL profile;
  - запуск полного локального контура через Docker Compose;
  - создание station и получение one-shot enrollment token;
  - установка агента на клиентский ПК;
  - настройка service account и DPAPI credential;
  - управление агентом с админского ПК;
  - refresh command, heartbeat и troubleshooting;
  - безопасный re-enrollment и uninstall;
- показывать дату/версию документа и предупреждать об устаревших инструкциях.

### 31.05. Design system и reusable UI

- использовать lucide-react для единообразных и доступных иконок;
- выносить повторяемые элементы в presentation UI-компоненты:
  StatusBadge, MetricCard, SectionHeading, HelpHint, InfoNote;
- сохранять единый визуальный язык для интерактивных состояний, статусов и
  пояснений полей;
- не заменять иконки декоративными emoji или текстовыми символами.

## UI safety rules

- не хранить API password в localStorage, IndexedDB или build artifacts;
- не показывать credential/token после исходного шага регистрации;
- не отображать TrueNAS API key ни в UI, ни в Markdown content;
- каждое опасное поле имеет краткое объяснение, допустимые значения и
  последствия;
- disabled/stale/offline station нельзя выбрать для publish;
- unknown/stale не трактовать как healthy;
- UI отображает server errors/correlation ID, но не raw exception/secret;
- Markdown reader открывает только документы из статического allowlist.

## Проверки

- `npm run build`;
- API client tests для Basic Auth, 401 и malformed response;
- knowledge registry test: все документы доступны, secret scan чистый;
- component/page tests для login, station status, selection gate и Markdown
  reader;
- manual visual check на desktop viewport;
- production build не содержит `BASIC_AUTH_PASSWORD`, TrueNAS API key,
  `AGENT_COMMAND_SIGNING_PRIVATE_KEY` или agent credential.

## Текущий срез

- [x] создан план frontend и зафиксированы требования к пояснениям,
  инструкциям и Markdown reader;
- [x] создан минимальный Vite shell, login, stations read/create и knowledge
  base reader;
- [x] подключён lucide-react, добавлен переиспользуемый UI-слой для метрик,
  статусов, заголовков и подсказок;
- [x] npm run build прошёл; headed visual smoke-check login пройден без
  browser errors;
- [x] добавлен publish wizard: выбор только online stations, dry_run/hot
  switch пояснения, server preflight, явное подтверждение и dispatch;
- [x] backend presentation routes prepare/dispatch добавлены и покрыты
  HTTP-контрактными тестами;
- [x] подключён GET publish job read model: polling, target progress,
  terminal states и recovery_required UI;
- [x] добавлен быстрый onboarding клиента: allowlisted Markdown-инструкция,
  вставка и проверка station report в форме создания station;
- [x] добавить ключевые frontend tests для API Basic Auth/error mapping,
  station selection и allowlisted knowledge registry;
- [x] добавить frontend в локальный Compose вместе с PostgreSQL и Redis;
- [x] расширить visual check на авторизованные экраны через временный SQLite
  backend contract: overview, stations, publish wizard и knowledge base;
- [x] Compose runtime backend/frontend и PostgreSQL startup migration проверены;
  `/api/v1/stations` через Basic Auth вернул `200`.

## Запреты

- не добавлять реальные секреты в `.env`, Markdown и bundle;
- не вызывать TrueNAS из browser;
- не реализовывать frontend-only обход backend safety gate;
- не показывать fake success для неподдержанных backend операций.
