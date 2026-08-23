# 25. Safe publish dispatch gate

## Цель

Разрешить постановку publish job в Dramatiq только после persisted preflight и
явного подтверждения оператора. Dispatch переводит job из
`awaiting_confirmation` в `publishing`, коммитит это состояние короткой UoW и
только затем передаёт минимальный payload queue port.

## Scope

- application `DispatchPublishJobUseCase` загружает job/targets заново;
- допустим только `awaiting_confirmation`;
- `client_confirmation=True` обязателен;
- каждый selected target должен иметь preflight `pass` или `warning`;
- `block`, `unknown`, отсутствующий report, error/recovery и пустой selection
  не enqueue-ятся;
- persistence commit происходит до вызова queue adapter; outbox/recovery
  улучшение остаётся отдельным планом.

## Ключевые тесты

- ready job переходит в `publishing` и enqueue получает только IDs;
- UoW закрыт до queue call;
- missing confirmation, wrong state и unsafe target не enqueue-ятся;
- successful target selection остаётся независимой от будущего worker;
- no Redis broker/NAS calls.

## Запреты

Не выполнять Fake/TrueNAS storage workflow, mapping switch, cleanup, destroy или
real Redis broker execution. Не помещать job state, mapping или secrets в task.

## Критерий завершения

Dispatch gate и tests проходят Ruff/pytest, `STATE.md` показывает следующий
шаг — outbox/retry semantics или отдельный worker fake executor stage.

## Статус

- [x] scope и transition/queue boundary зафиксированы;
- [x] dispatch use case создан;
- [x] ключевые tests созданы;
- [x] Ruff и pytest пройдены;
- [x] `STATE.md` обновлён.

Подшаг завершён. Job переходит в `publishing` до queue call; commit/send gap
явно оставлен следующим outbox/retry планом.
