# 14. Read-only API: health, stations и Basic Auth

## Цель

Поднять минимальный HTTP-контур поверх application use case: health endpoint,
список станций и HTTP Basic Auth. API не выполняет SQL и не знает TrueNAS
методов; concrete зависимости собираются в `main.py`.

## Изменяемые модели

Новые domain-сущности не добавляются. Используются:

- `domain.station.Station` как application output;
- `presentation` response DTO для публичной формы станции;
- `Basic Auth` operator identity с фиксированным логином `admin` и секретом из
  `BASIC_AUTH_PASSWORD`.

## API routes

- `GET /health` — минимальный liveness/readiness ответ процесса;
- `GET /api/v1/stations` — список не удалённых enabled станций;
- `GET /api/v1/stations?include_disabled=true` — список также disabled,
  но без soft-deleted станций.

Оба endpoint защищены Basic Auth. Отсутствующий пароль конфигурации — fail
closed, а не fallback на значение из репозитория.

## Migration plan

- добавить Alembic config/env, импортирующие `repository.models.Base.metadata`;
- URL БД читать из `DATABASE_URL`;
- revision в этом подшаге не генерировать и не применять;
- production migration выполнять только отдельной явной командой после review.

## Ключевые тесты

- application use case вызывает UoW и возвращает stations;
- Basic Auth: valid credentials, invalid credentials, missing password;
- `/health` возвращает ожидаемый ответ;
- `/api/v1/stations` преобразует domain output в response и не содержит SQL;
- endpoint без credentials получает `401`.

Не тестировать отдельно Pydantic-поля без собственной логики и фреймворковую
регистрацию каждого маршрута.

## Запреты

- не выполнять миграции автоматически при импорте приложения;
- не хранить пароль в коде, планах или тестовых fixtures;
- не добавлять storage write/TrueNAS вызовы;
- не вызывать repository из presentation в обход application use case;
- не добавлять глобальный UoW или глобальную SQLAlchemy session.

## Критерий завершения

Приложение создаётся через composition root, API routes проходят ключевые
auth/application tests, `ruff` чистый, а Alembic только подготовлен к будущей
генерации revision.

## Статус

- [x] application station query создан;
- [x] auth boundary создан;
- [x] health/stations routes созданы;
- [x] Alembic config создан без revision/apply;
- [x] ключевые API/auth tests созданы;
- [x] проверки и `STATE.md` обновлены.

Подшаг завершён. Следующий безопасный подшаг read-only backend — station
registry/enrollment/heartbeat; текущий API не выполняет TrueNAS operations.
