# WebLab: HTTP GET /info

Простой сервер на FastAPI для демонстрации клиент-серверного взаимодействия по HTTP.

## Что реализовано

- Обработчик `GET /info`
- Ответ в формате JSON:

```json
{
  "days_before_new_year": 123
}
```

## Требования

- Python 3.10+
- `pip`
- (Опционально) Docker и Docker Compose

## Запуск локально

1. Установить зависимости:

```bash
pip install -r requirements.txt
```

2. Запустить сервер:

```bash
uvicorn app:app --host 0.0.0.0 --port 4200
```

3. Проверить endpoint:

```bash
curl --location "http://localhost:4200/info"
```

## Запуск через Docker

### Сборка и запуск через docker compose

```bash
docker compose up --build
```

### Проверка

```bash
curl --location "http://localhost:4200/info"
```

## Остановка контейнеров

```bash
docker compose down
```
