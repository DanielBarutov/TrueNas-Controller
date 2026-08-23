# Планы Game Update Controller

## Назначение

Эта папка — рабочий источник контекста проекта. Реализация выполняется последовательно по планам, а не по разрозненным задачам из переписки. Перед началом каждого этапа нужно открыть этот файл, дорожную карту и план текущего этапа.

Текущий статус проекта ведётся в корневом файле [STATE.md](../STATE.md): там отмечены активный, закрытые и открытые планы, чекапы и история решений.

Проект строится как безопасный контроллер публикации игровых обновлений на TrueNAS SCALE. MVP должен поддерживать произвольное количество станций, Windows-агент на клиентах и админском ПК, пошаговый preflight, mock-публикацию, верификацию, частичный успех и rollback.

## Ограничения из `CODEX.md`

- Не хардкодить количество ПК и имена `pc01`–`pc08`.
- Браузер работает только с собственным API приложения.
- TrueNAS API вызывается только backend/worker через versioned JSON-RPC 2.0 over WebSocket.
- Реальный NAS не подключать до отдельного согласования.
- До mock-тестов не писать реальные операции mapping switch и `destroy`.
- API key TrueNAS не попадает во frontend, Windows-агент, логи и репозиторий.
- `dry_run=true` — значение по умолчанию для publish, switch и cleanup.
- Старый рабочий mapping не удалять автоматически при ошибке.
- Один writable LUN нельзя одновременно подключать к нескольким Windows-ПК.
- `allow_hot_switch` выключен по умолчанию; политика по умолчанию — `idle_only`.
- Перед каждым следующим этапом показывать план, изменяемые модели и тесты.
- Durable worker: **Dramatiq**, broker — Redis.
- Авторизация нашего приложения: **HTTP Basic Auth**, пользователь `admin`.
- Пароль приложения задаётся через `BASIC_AUTH_PASSWORD` и не записывается в репозиторий. Передавать Basic Auth только по HTTPS.

## Правила ведения планов

1. Каждый план имеет номер и находится в отдельной папке.
2. В начале плана фиксируются цель, входы, выходы, зависимости и запреты.
3. После завершения этапа в плане отмечаются фактически выполненные пункты, проверки и открытые вопросы.
4. Новое решение сначала заносится в раздел «Решения и инварианты», затем реализуется.
5. Если реализация расходится с планом, сначала обновляется план с причиной расхождения.
6. Не считать структурную проверку доказательством runtime-, визуальной или интеграционной корректности.

## Карта планов

| План | Содержание | Состояние |
|---|---|---|
| [00-context](00-context.md) | Исходные требования, границы MVP и словарь | готов |
| [01-architecture](01-architecture/01-layers.md) | Слои, зависимости и потоки данных | готов |
| [02-database](02-database/01-schema.md) | Сущности, связи, ограничения и миграции | готов |
| [03-state-machine](03-state-machine/01-state-machine.md) | Состояния станций, заданий и переходы | готов |
| [04-security](04-security/01-security.md) | Угрозы, секреты, авторизация и аудит | готов |
| [05-api](05-api/01-contract.md) | Контракты собственного API и событий | готов |
| [06-agent](06-agent/01-windows-agent.md) | Windows-агент, snapshot и enrollment | готов |
| [06.02-agent-command-delivery](06-agent/02-command-delivery.md) | Подписанные refresh-команды, lease и ack | открыт |
| [07-truenas-adapter](07-truenas-adapter/01-adapter.md) | Adapter, mock, fixtures и интеграционный gate | готов |
| [08-workflows](08-workflows/01-publish-workflow.md) | Preflight, publish, switch, verify, rollback | готов |
| [09-testing](09-testing/01-strategy.md) | Пирамида тестов и критерии доказательности | готов |
| [10-implementation-roadmap](10-implementation-roadmap/01-roadmap.md) | Последовательность реализации | готов |
| [11-project-rules](11-project-rules/01-development-rules.md) | Правила чистой архитектуры, SOLID, UoW, Protocol, тестов и Ruff | готов |
| [12-read-only-backend](12-read-only-backend/01-bootstrap.md) | Bootstrap каркаса read-only backend | завершён |
| [13-persistence](13-persistence/01-models-uow.md) | SQLAlchemy models, repository и concrete UoW | завершён |
| [14-read-only-api](14-read-only-api/01-health-stations-auth.md) | Health, stations read API и Basic Auth | завершён |
| [15-agent-lifecycle](15-agent-lifecycle/01-registry-enrollment-heartbeat.md) | Station registry, enrollment и heartbeat | завершён |
| [16-preflight-core](16-preflight-core/01-process-rules-evaluator.md) | Process rules и preflight evaluator | завершён |
| [17-preflight-api](17-preflight-api/01-rules-snapshot-query.md) | Rules persistence, latest snapshot и preflight API | завершён |
| [18-wizard-gating](18-wizard-gating/01-confirmation-selection-gate.md) | Human confirmation и selection safety gate | завершён |
| [19-mock-publish](19-mock-publish/01-dramatiq-fake-workflow.md) | Draft publish job, fake workflow и Dramatiq boundary | завершён |
| [20-publish-persistence](20-publish-persistence/01-job-target-uow.md) | `publish_jobs`/`publish_targets`, repositories и worker composition | завершён |
| [21-draft-command](21-draft-command/01-create-and-enqueue.md) | Создание draft, idempotency и queue port | завершён |
| [22-publish-presentation](22-publish-presentation/01-create-draft-route.md) | Basic Auth route создания publish draft | завершён |
| [23-publish-read-model](23-publish-read-model/01-job-status-query.md) | GET job read model и target outcomes | завершён |
| [24-publish-confirmation](24-publish-confirmation/01-confirmation-command.md) | Operator confirmation и persisted preflight gate | завершён |
| [25-publish-dispatch](25-publish-dispatch/01-safe-enqueue-gate.md) | Safe transition в publishing и enqueue gate | завершён |
| [26-publish-outbox](26-publish-outbox/01-transactional-outbox-retry.md) | Transactional outbox и relay retry semantics | завершён |
| [27-fake-worker-executor](27-fake-worker-executor/01-persisted-workflow-results.md) | Fake workflow results в persisted job/targets | завершён |
| [28-fake-acceptance](28-fake-acceptance/01-end-to-end-pipeline.md) | End-to-end fake publish pipeline acceptance | завершён |
| [29-truenas-read-only](29-truenas-read-only/01-versioned-adapter-contract.md) | Versioned TrueNAS read-only adapter contract | завершён |
| [30-truenas-lan-gate](30-truenas-lan-gate/01-local-api-docs-and-connection.md) | Проверка версии и локальной схемы NAS перед opt-in LAN smoke check | открыт |
| [31-frontend](31-frontend/01-operator-ui-and-knowledge-base.md) | Операторский React/Vite UI, Lucide/reusable components, пояснения полей и Markdown-база знаний | в работе |

## Текущий этап

**Этап 2 — каркас и read-only backend.** Bootstrap и persistence-подшаг для
`stations`/`agents`, agent lifecycle, preflight core/API, wizard gating,
deterministic fake publish workflow, job/target persistence, Dramatiq
composition handler и application draft/queue boundary выполнены. Versioned
TrueNAS read-only adapter contract завершён; следующий gate — проверка
конкретного локального `/api/docs/`, storage write и реальный NAS по-прежнему
запрещены.

## Принятые решения

1. Worker — **Dramatiq**. Redis используется как broker/backend координации.
2. Для собственного API/UI — **HTTP Basic Auth** с логином `admin`. Пароль хранится только во внешней runtime-конфигурации `BASIC_AUTH_PASSWORD`; в планы и git его не записываем.
3. Официальные TrueNAS-документы и найденные API-методы зафиксированы в [`docs/ONLINE_DOCS.md`](../docs/ONLINE_DOCS.md). Реальный NAS пока не подключён.
4. Правила разработки зафиксированы в [`PROJECT_RULES.md`](../PROJECT_RULES.md) и корневом `pyproject.toml`.
5. Автоматическая проверка версии игры не входит в MVP: факт обновления подтверждает оператор, а приложение проверяет только технический результат публикации.

## Открытые решения

- Фактическая версия конкретного NAS и проверка его локального `/api/docs/`.
