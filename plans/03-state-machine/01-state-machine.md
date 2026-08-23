# 03. State machine

## Цель

Сделать workflow явным и запретить переходы, которые могут привести к переключению неподготовленной станции или потере старой версии.

## Состояния станции

| Состояние | Смысл | Можно выбрать для publish |
|---|---|---|
| `offline` | heartbeat отсутствует дольше offline threshold | нет |
| `stale` | агент отвечает, но snapshot устарел | нет |
| `online` | heartbeat свежий, но preflight ещё не пройден | нет до preflight |
| `blocked` | есть blocking process/drive/mapping issue | нет |
| `ready` | свежие проверки успешны | да |
| `switching` | над станцией выполняется switch | нет |
| `verified` | последняя операция успешно подтверждена | да для следующего job |
| `error` | последняя операция завершилась ошибкой | только после нового preflight |

Переход `online → ready` возможен только application service после актуального preflight. Устаревший успешный snapshot не поддерживает `ready`.

## Состояния job

```text
draft
  → preflight
  → waiting_for_admin
  → awaiting_client_confirmation
  → publishing
  → switching
  → verifying
  → completed
  → partial_failure
  → failed
```

Из любого apply-состояния оператор может запросить `cancel`, но cancellation не прерывает бездумно уже начатую storage-операцию: worker завершает безопасную текущую стадию и переводит job в `failed`/`partial_failure` с причиной.

Rollback — отдельная операция над `publish_target`, а не переход всего job назад. Успешный rollback target получает `rolled_back`; job получает `rolled_back` только если это соответствует политике итогового отчёта.

## Шаги wizard

| Шаг | Вход | Успех | Блокировка |
|---|---|---|---|
| 0 draft | label/description/mode | создан job | invalid input, duplicate idempotency |
| 1 admin check | fresh admin snapshot | admin preflight passed | blocking process, stale/offline |
| 2 confirmation | явное «Да» | audit confirmation | «Нет» или отсутствие ответа |
| 3 client preflight | selected station IDs | target rows ready | stale, process, drive, mapping, busy |
| 4 master publish | all required checks | one master version | NAS/mock error, duplicate object |
| 5 switch | per-target approval | target switched or preserved old | unsafe mapping, idle policy, timeout |
| 6 verify | fresh agent + adapter reads | target verified/error | технический target/mapping mismatch |
| 7 finish | all target results | completed/partial_failure | unresolved worker state |

## Формат перехода

Каждый переход должен иметь:

- `from_state`, `to_state`;
- actor (`operator`, `worker`, `agent`, `system`);
- command ID и correlation ID;
- preconditions;
- audit event;
- compensation/next recovery action;
- reason при отказе.

## Инварианты

1. Нельзя выполнить switch, если target не прошёл текущий preflight.
2. Нельзя выполнить switch к mapping, который не подтверждён adapter read-back.
3. `dry_run=true` не меняет NAS и помечает результат как simulation.
4. `allow_hot_switch=false` требует свежего idle подтверждения агента.
5. Ошибка одного target не переводит успешные target в error.
6. Старый mapping сохраняется до `verified`.
7. Повтор worker task безопасен на каждой стадии.
8. Cleanup не является частью обычного finish.

## Идемпотентность стадий

- **master**: ключ `(job_id, master_label)`; при повторе найти существующий объект и сверить metadata.
- **clone**: ключ `(job_id, station_id)`; повтор не создаёт второй clone.
- **switch**: если read-back уже показывает ожидаемый mapping, записать success без повторного опасного действия.
- **verify**: повторить read-only checks с новым snapshot.
- **rollback**: если старый mapping уже восстановлен, вернуть idempotent success.

## Неопределённое состояние

Если worker потерял связь после apply-запроса, target переводится в `switch_unknown`, а не сразу в error. Recovery сначала выполняет read-back текущего mapping, затем выбирает `verified`, `error` или требует ручного вмешательства. Автоматически уничтожать объекты нельзя.
