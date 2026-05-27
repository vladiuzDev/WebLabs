# WebLab: ЛР3 — Авторизация и аутентификация (JWT, OAuth2, Cookies)

## Описание
REST API на FastAPI с системой авторизации через JWT токены и OAuth2 (Яндекс ID).
Продолжение ЛР2 — все endpoints `/items` защищены авторизацией.

## Стек
- FastAPI
- SQLAlchemy + Alembic
- PostgreSQL
- bcrypt (хеширование паролей)
- python-jose (JWT)
- httpx (OAuth запросы)
- Docker + Docker Compose

## Запуск
```bash
cp .env.example .env
# заполни .env своими значениями
docker compose up --build
```

## Endpoints

### Auth
| Метод | URI | Описание |
|---|---|---|
| POST | /auth/register | Регистрация |
| POST | /auth/login | Вход |
| POST | /auth/refresh | Обновление токенов |
| GET | /auth/whoami | Текущий пользователь |
| POST | /auth/logout | Выход |
| POST | /auth/logout-all | Выход со всех устройств |
| GET | /auth/oauth/yandex | Вход через Яндекс |
| POST | /auth/forgot-password | Запрос сброса пароля |
| POST | /auth/reset-password | Сброс пароля |

### Items (требуется авторизация)
| Метод | URI | Описание |
|---|---|---|
| GET | /items | Список items |
| POST | /items | Создать item |
| GET | /items/{id} | Получить item |
| PUT | /items/{id} | Обновить item |
| PATCH | /items/{id} | Частично обновить item |
| DELETE | /items/{id} | Удалить item |

## .env.example
```
DB_HOST=postgres
DB_PORT=5432
DB_USER=student
DB_PASSWORD=your_password
DB_NAME=wp_labs
PORT=4200

JWT_ACCESS_SECRET=your_access_secret
JWT_REFRESH_SECRET=your_refresh_secret
JWT_ACCESS_EXPIRATION=15m
JWT_REFRESH_EXPIRATION=7d

CLIENT_ID=your_yandex_client_id
CLIENT_SECRET=your_yandex_client_secret
CALLBACK_URL=http://localhost:4200/auth/oauth/yandex/callback
```