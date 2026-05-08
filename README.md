# WebLab: ЛР2 REST API (FastAPI + PostgreSQL)

Продолжение ЛР1: реализован REST API с PostgreSQL, ORM, миграциями, soft delete и пагинацией.

## Стек

- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL 16+
- Docker / Docker Compose

## Переменные окружения

Скопируйте пример и при необходимости измените значения:

```bash
cp .env.example .env
```

Пример `.env`:

```env
DB_HOST=postgres
DB_PORT=5432
DB_USER=student
DB_PASSWORD=student_secure_password
DB_NAME=wp_labs
PORT=4200
```

## Запуск через Docker (рекомендуется)

```bash
docker compose up --build
```

При старте контейнера приложения автоматически выполняется:

```bash
alembic upgrade head
```

Остановка:

```bash
docker compose down
```

## Запуск локально (без Docker)

1. Установить зависимости:

```bash
pip install -r requirements.txt
```

2. Поднять PostgreSQL и настроить `.env`.

3. Применить миграции:

```bash
alembic upgrade head
```

4. Запустить API:

```bash
uvicorn app:app --host 0.0.0.0 --port 4200
```

## API

### Служебный endpoint из ЛР1

- `GET /info` — количество дней до Нового года.

### Ресурс `items`

- `GET /items?page=1&limit=10` — список активных элементов с пагинацией (`200`)
- `GET /items/{id}` — активный элемент по id (`200`)
- `POST /items` — создать элемент (`201`)
- `PUT /items/{id}` — полное обновление (`200`)
- `PATCH /items/{id}` — частичное обновление (`200`)
- `DELETE /items/{id}` — мягкое удаление (`204`)

`DELETE` выполняет только soft delete (заполняется `deleted_at`).
Удаленные записи не возвращаются в `GET /items` и `GET /items/{id}`.

### Пагинация

Параметры:
- `page` (по умолчанию `1`, должно быть `> 0`)
- `limit` (по умолчанию `10`, диапазон `1..100`)

Формат ответа списка:

```json
{
  "data": [],
  "meta": {
    "total": 0,
    "page": 1,
    "limit": 10,
    "totalPages": 0
  }
}
```

## Примеры запросов (cURL / Postman)

Создание:

```bash
curl.exe -X POST "http://localhost:4200/items" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"Item 1\",\"description\":\"Test item\",\"status\":\"active\"}"
```

Список:

```bash
curl.exe -X GET "http://localhost:4200/items?page=1&limit=5"
```

Удаление:

```bash
curl.exe -X DELETE "http://localhost:4200/items/<ITEM_ID>"
```
