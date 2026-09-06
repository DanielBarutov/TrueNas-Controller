# Реестр dataset и автоматическая очистка

Каждый live publish после создания clone сохраняет в `publish_artifacts`:

- job и station;
- исходный dataset, имя созданного dataset и snapshot;
- mapping, с которым dataset был назначен extent;
- время создания;
- `current`, `retired`, `deleted` или `cleanup_failed`.

Подробности видны в Controller UI через **История обновлений → Подробнее**.

## Настройка worker

Cleanup — это задача внутри Dramatiq worker: она запускается либо из меню по
чекбоксам, либо периодически при включённом scheduler. В `.env`
можно задать:

```dotenv
DATASET_CLEANUP_ENABLED=false
DATASET_CLEANUP_INTERVAL_SECONDS=604800
DATASET_CLEANUP_RETENTION_DAYS=30
DATASET_CLEANUP_BATCH_SIZE=10
TRUENAS_CLEANUP_APPLY_ENABLED=true
```

По умолчанию интервал равен 7 дням, retention — 30 дней, batch — 10 записей.
`DATASET_CLEANUP_ENABLED=false` оставляет автоматический retention выключенным:
удаление запускается только из меню по выбранным чекбоксам. Для фактического
удаления нужны корректные `TRUENAS_WS_URL`/`TRUENAS_API_KEY` и
`TRUENAS_CLEANUP_APPLY_ENABLED=true`; publish-gate и
`PUBLISH_EXECUTOR_MODE=truenas` для этого не требуются.

В удаление попадают только записи, которые:

- не являются текущим dataset станции;
- не помечены `deleted`;
- старше retention;
- записаны Controller после live publish.

Удаление не рекурсивное и не force. Ответ TrueNAS `null` для уже отсутствующего
dataset считается успешным идемпотентным результатом. Ошибка сохраняется как
`cleanup_failed` и попадёт в следующую попытку.

После изменения `.env` пересоздайте worker:

```powershell
docker compose up -d --build worker
docker compose logs -f worker
```

Реализованный метод проверен по официальному контракту
[`pool.dataset.delete`](https://api.truenas.com/v25.10.0/api_methods_pool.dataset.delete.html).
