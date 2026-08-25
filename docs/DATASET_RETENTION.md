# Реестр dataset и автоматическая очистка

Каждый live publish после создания clone сохраняет в `publish_artifacts`:

- job и station;
- исходный dataset, имя созданного dataset и snapshot;
- mapping, с которым dataset был назначен extent;
- время создания;
- `current`, `retired`, `deleted` или `cleanup_failed`.

Подробности видны в Controller UI через **История обновлений → Подробнее**.

## Настройка worker

Cleanup — это отдельная периодическая задача внутри Dramatiq worker. В `.env`
можно задать:

```dotenv
DATASET_CLEANUP_ENABLED=true
DATASET_CLEANUP_INTERVAL_SECONDS=604800
DATASET_CLEANUP_RETENTION_DAYS=30
DATASET_CLEANUP_BATCH_SIZE=10
TRUENAS_CLEANUP_APPLY_ENABLED=false
```

По умолчанию интервал равен 7 дням, retention — 30 дней, batch — 10 записей.
Сначала оставляйте `TRUENAS_CLEANUP_APPLY_ENABLED=false`: worker только
читает кандидатов и пишет их количество в лог. Для фактического удаления
нужно отдельно включить этот флаг, `PUBLISH_EXECUTOR_MODE=truenas`, корректный
`TRUENAS_API_KEY` и общий `TRUENAS_APPLY_ENABLED=true`.

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
