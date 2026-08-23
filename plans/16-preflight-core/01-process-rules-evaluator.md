# 16. Preflight core и process rules

## Цель

Вынести критичные preflight-инварианты в чистый domain/application core до
подключения job/publish workflow. Evaluator должен одинаково работать для fake
snapshot и будущего Windows-agent payload.

## Изменяемые модели

- `ProcessRule`: normalized process name, station role, enabled flag,
  `required_closed`, severity и persistent policy;
- `PreflightPolicy`: freshness threshold, required drive и free-space threshold;
- `CheckResult`: `pass`, `block`, `unknown`, `warning`, code/message/source;
- `PreflightReport`: aggregate status, checks и `can_publish` invariant.

## API routes

В этом подшаге routes не добавляются. Сначала проверяется чистый evaluator;
station snapshot/rules repository и `POST /preflight` будут следующим подшагом.

## Migration plan

Миграции не создаются. Persistence для `process_rules` и preflight results
добавляется после утверждения domain evaluator.

## Ключевые тесты

- blocking required-closed process -> `block`;
- warning rule не блокирует publish;
- missing snapshot/stale snapshot -> `unknown`;
- missing `D:`/low free space -> `block`;
- all checks pass -> `can_publish=True`;
- `unknown` никогда не преобразуется в pass.

## Запреты

- не завершать процессы;
- не выполнять network/SQL/TrueNAS calls;
- не считать stale snapshot зелёным;
- не добавлять publish/switch/cleanup.

## Критерий завершения

Evaluator остаётся чистым Python, покрывает ключевые blocking/unknown
инварианты, не зависит от FastAPI/SQLAlchemy/psutil, а `STATE.md` фиксирует
готовность к persistence/API preflight подшагу.

## Статус

- [x] domain preflight models созданы;
- [x] evaluator создан;
- [x] ключевые preflight tests созданы;
- [x] проверки выполнены;
- [x] `STATE.md` обновлён.

Подшаг завершён. В evaluator зафиксированы station/snapshot binding,
disabled-station block и правило `unknown != pass`. Следующий шаг — persistence
для process rules и preflight API/application boundary.
