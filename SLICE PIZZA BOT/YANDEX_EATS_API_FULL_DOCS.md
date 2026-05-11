# Yandex Eats Partner API — Полная сводка документации

Собрано: 2026-05-12 на основе официальной документации
`https://yandex.ru/dev/eda-vendor/doc/ru/`.

> **Важно:** Yandex Eats Partner API — **двунаправленный**:
>
> * **Pull-направление** (партнёр → Yandex): партнёр сам ходит на хосты Яндекс.Еды
>   (`https://api.eda.yandex.ru` / `https://vendor.eda.yandex.net`), чтобы получить
>   меню, статусы заказов, отзывы.
> * **Push-направление** (Yandex → партнёр): Yandex стучит в наши endpoint'ы
>   `POST /order`, `PUT /order/{id}/status`, `POST /v1/feedback`. Раздел
>   **«Vendor Management Integration API»** — это методы, которые **партнёр
>   реализует на своей стороне** (мы — server), а Yandex Eats — клиент.

## 1. Аутентификация — OAuth 2.0 (Client Credentials)

Базовый OAuth-эндпоинт:
```
POST /oauth2/token
Host: vendor.eda.yandex.net   (или api.eda.yandex.ru для pull-методов)
Content-Type: application/x-www-form-urlencoded

client_id=<from cabinet>&client_secret=<from cabinet>
```

Ответ (200 OK):
```json
{
  "access_token": "bqehYcfk7Tb2zKRkxQ-IaK9nHyntdYnlpJ7kwTNX3B6mIKPws",
  "expires_in": 120,
  "scope": "vendor_management",
  "token_type": "bearer"
}
```

**Ключевые особенности:**
- `expires_in` маленький (часто 120 секунд!) — токен надо **кэшировать в памяти**
  и обновлять заранее (например, при `expires_in - 30s`).
- `grant_type` НЕ требуется (нестандартная реализация Яндекса).
- Сохраняем токен в памяти процесса (не в БД) — он короткоживущий.

**curl-пример:**
```bash
curl -X POST 'https://vendor.eda.yandex.net/oauth2/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=YOUR_ID&client_secret=YOUR_SECRET'
```

Все последующие запросы — с `Authorization: Bearer <access_token>`.

## 2. Где взять client_id и client_secret в кабинете Я.Еды

Точный путь в кабинете `https://vendor.eda.yandex/home`:

```
Войти → выбрать ресторан «Миа пицца на Княжьем озере»
  → шестерёнка / «Настройки» (Settings) в левой панели
    → раздел «Интеграции» (Integrations) или «API»
      → блок «Партнёрское API» / «Vendor Management Integration»
        → кнопка «Создать ключи» / «Сгенерировать»
```

Альтернативные местоположения, если выше не нашлось:
1. **«Профиль партнёра»** → «Доступы для разработчиков» — в правом верхнем углу
   меню рядом с аватаром.
2. **«Интеграция с POS / iiko»** → внизу страницы блок «Прямая интеграция API»
   с client_id/client_secret.
3. **«Документация партнёра»** → ссылка «Запросить API-доступ» (тогда выпадает
   модалка с client_id, а secret приходит на email Пётра `pete.braslavskii@yandex.ru`).

Если client_id виден, а client_secret скрыт — рядом будет кнопка «Показать»
или «Скопировать». Пётр должен **скопировать оба значения** и переслать
через зашифрованный канал. Мы кладём в `.env`:
```
YANDEX_EATS_CLIENT_ID=...
YANDEX_EATS_CLIENT_SECRET=...
```

## 3. Базовые URL

| Назначение | URL |
| --- | --- |
| OAuth Vendor | `https://vendor.eda.yandex.net` |
| Pull (мы → Yandex): меню, наличие, отзывы | `https://api.eda.yandex.ru` |
| Push (Yandex → мы) — мы реализуем endpoint'ы | наш сервер (`https://api.slicepizza.ru/webhook/yandex-eats`) |

> Note: ряд push-методов внутреннего управления упоминает `http://dc-partner.eda.yandex.net` — это закрытый network инстанс, доступный только из инфраструктуры Яндекса; через интернет он недоступен.

## 4. Меню (Pull)

### 4.1 `GET /menu/{restaurantId}/composition` — получить меню
- Headers: `Authorization: Bearer ...`, `Accept: application/vnd.eats.menu.composition.v2+json`
- Response:
  ```json
  {
    "schedules": {...},
    "categories": [{"id": "...", "name": "..."}],
    "items": [{"id": "...", "name": "...", "price": 540, "modifiers": [...], "images": [...]}],
    "combos": [...],
    "lastChange": "2026-05-12T08:00:00.000+03:00"
  }
  ```

### 4.2 `GET /menu/{restaurantId}/availability` — стоп-лист
- Response:
  ```json
  {
    "items":     [{"itemId": "pizza_margarita", "stock": 0}],
    "modifiers": [{"modifierId": "extra_cheese", "stock": 0}],
    "combos":    [{"comboId": "combo_a", "stock": 0}]
  }
  ```
- `stock: 0` — позиция в стоп-листе.

### 4.3 `POST /menu/import/initiation` — форс-парсинг меню
- Заставляет Яндекс пересчитать наше меню (если он его сам тянет, либо после
  ручной правки кабинетом).
- Body: `{"restaurant_ids": ["<place_id>"]}`

## 5. Заказы

Все методы заказов — это **push от Яндекса нам** (Yandex Eats звонит в наш `https://api.slicepizza.ru/webhook/yandex-eats/...`).

| Метод | URL (наш) | Назначение |
| --- | --- | --- |
| `POST /order` | мы | Создать заказ (`partner.order.create`) |
| `GET  /order/{orderId}` | мы | Получить заказ |
| `PUT  /order/{orderId}` | мы | Обновить (например, состав) |
| `DELETE /order/{orderId}` | мы | Отменить |
| `GET  /order/{orderId}/status` | мы | Текущий статус |
| `PUT  /order/{orderId}/status` | мы | Yandex меняет статус (CANCELLED / TAKEN_BY_COURIER / DELIVERED) |
| `POST /order/{orderId}/courier` | мы | Обновить инфо о курьере |

### 5.1 `POST /order` — приём нового заказа
Headers от Yandex:
- `Authorization: Bearer <их JWT, мы должны его валидировать через jwks или shared-secret>`
- `Content-Type: application/vnd.eats.order.v2+json`

Body (упрощённый):
```json
{
  "platform": "YE",
  "discriminator": "yandex",          // yandex | marketplace | pickup
  "eatsId": "260512-12345678",
  "restaurantId": "286411",
  "items": [
    {
      "id": "pizza_margarita",
      "name": "Маргарита",
      "quantity": 2,
      "price": 790,
      "modifications": [...],
      "promos": [...]
    }
  ],
  "persons": 1,
  "comment": "позвонить за 5 мин",
  "deliveryInfo": {
    "clientName": "Алексей",
    "phoneNumber": "+79991234567",
    "realPhoneNumber": "+79991234567",
    "pickupCode": "8742",
    "courierArrivementDate": "2026-05-12T11:30:00+03:00"
  },
  "paymentInfo": {
    "itemsCost": 1580,
    "deliveryFee": 0,
    "total": 1580,
    "paymentType": "CARD"
  }
}
```

Response (200 OK) — наш ответ:
```json
{"result": "OK", "orderId": "slice-uuid-here"}
```

### 5.2 `PUT /order/{orderId}/status` — Yandex шлёт статус
```json
{
  "status": "CANCELLED|TAKEN_BY_COURIER|DELIVERED",
  "attributes": ["paid"],
  "comment": "...",
  "reason": "...",            // только при CANCELLED
  "updatedAt": "2026-05-12T11:00:00.000+03:00"
}
```
Ответ — `204 No Content`.

## 6. Отзывы

### 6.1 `POST /v1/feedback` — push отзыва от Yandex нам
```json
{
  "feedback": {
    "id": "fb-123",
    "orderId": "...",
    "rating": 5,
    "comment": "Отличная пицца",
    "restaurantId": "286411",
    "eatsId": "260512-12345678",
    "createdAt": "2026-05-12T12:00:00+03:00",
    "takenAt": "...",
    "deliveredAt": "..."
  },
  "orderInfo": {...}
}
```
Ответ: `{"result": "OK"}`.

### 6.2 Reply (через Vendor Management)
`POST /feedback-answer` (на dc-partner-инфраструктуру; **доступен через
business-side, не публично из интернета** — поэтому используем pull-эндпоинт
`POST /4.0/restapp-front/eats-place-rating/v1/feedbacks/{id}/answer`, если у нас
есть session cookie, см. `services/yandex_vendor.py`).

## 7. Vendor Management Integration API (push нами в Яндекс)

Реализованы как сервис → сервис (через `dc-partner.eda.yandex.net`). Список:

| Endpoint | Назначение |
| --- | --- |
| `POST /oauth2/token` | Получить токен |
| `POST /block` | Заблокировать ресторан (например, на время обеда персонала) |
| `POST /unblock` | Разблокировать |
| `POST /v2/status` | Список текущих блокировок |
| `POST /feedback-answer` | Ответить на отзыв (текст + промокод) |
| `POST /menu/import/initiation` | Форс-перепарсинг меню |
| `POST /platform/orders/{orderId}/codes/validate` | Проверить курьерский код |
| `POST /partner/orders/history` | История заказов |
| `POST /partner/integration/v1/get-orders-details` | Подробности заказов |
| `POST /partner/external/busy-mode/status` | Список ресторанов в режиме повышенного спроса |

## 8. Лимиты, retry, формат дат

- Все даты — ISO 8601 с явной таймзоной (`+03:00` для МСК).
- Цена — `decimal` в **рублях**, но кратно `0.01`. Мы будем хранить копейки и
  делить на 100 при отправке.
- TTL токена ~120s. Кэшируем в памяти, рефрешим при `<30s` оставшихся.
- Retry: на 5xx и сетевые ошибки — 3 ретрая c экспо-бэкоффом 2/4/8 секунд.
  401 — единичный refresh-токен и одна попытка повтора. 4xx — fail-fast.
- Rate limit: документация не даёт явных цифр, но опытным путём `> 5 req/sec`
  на один client_id приводит к 429 → respect `Retry-After`.

## 9. Webhook authentication (Yandex → нам)

Документация на дату 2026-05-12 не описывает HMAC-подпись webhook'ов. Поэтому
используем:
1. **IP allowlist** (Yandex Cloud DC IPs — динамические, поэтому пока не
   жёстко-ограничиваем).
2. **Shared static token** в `X-Yandex-Auth-Token` header — мы кладём в
   `YANDEX_EATS_WEBHOOK_TOKEN` и сравниваем `hmac.compare_digest`.
3. **TLS** — обязательно. Yandex не шлёт на чистый HTTP.

Точный механизм аутентификации webhooks ещё будет уточнён у менеджера
интеграции Яндекса — пока используем shared-secret approach.

## 10. Примеры curl

### Получить токен
```bash
curl -X POST 'https://vendor.eda.yandex.net/oauth2/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=YOUR_ID&client_secret=YOUR_SECRET'
```

### Получить меню
```bash
TOKEN=$(curl -s -X POST 'https://vendor.eda.yandex.net/oauth2/token' \
  -d 'client_id=...&client_secret=...' | jq -r .access_token)

curl -X GET "https://api.eda.yandex.ru/menu/286411/composition" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.eats.menu.composition.v2+json"
```

### Заблокировать ресторан на 30 минут
```bash
curl -X POST 'https://vendor.eda.yandex.net/block' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "restaurant_ids": ["286411"],
    "from": "2026-05-12T13:00:00+03:00",
    "to":   "2026-05-12T13:30:00+03:00",
    "reason": "Тех. перерыв"
  }'
```

### Ответить на отзыв
```bash
curl -X POST 'https://vendor.eda.yandex.net/feedback-answer' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "feedback_id": "fb-123",
    "text": "Спасибо! Ждём вас снова.",
    "promo_discount": 10
  }'
```

## 11. Источники

- Overview: <https://yandex.ru/dev/eda-vendor/doc/ru/>
- Reference: <https://yandex.ru/dev/eda-vendor/doc/ru/ref/>
- Menu: <https://yandex.ru/dev/eda-vendor/doc/ru/ref/Menyu/>
- Orders: <https://yandex.ru/dev/eda-vendor/doc/ru/ref/Zakazy/>
- Vendor Mgmt: <https://yandex.ru/dev/eda-vendor/doc/ru/ref/Vendor-Management-Integration-API/>
- OAuth ref: <https://yandex.ru/dev/eda-vendor/doc/ru/ref/Vendor-Management-Integration-API/BlocksAuth>
- partner.menu.get: <https://yandex.ru/dev/eda-vendor/doc/ru/ref/Menyu/partner.menu.get>
- partner.availability.get: <https://yandex.ru/dev/eda-vendor/doc/ru/ref/Menyu/partner.availability.get>
- partner.order.create: <https://yandex.ru/dev/eda-vendor/doc/ru/ref/Zakazy/partner.order.create>
- partner.order.status.put: <https://yandex.ru/dev/eda-vendor/doc/ru/ref/Zakazy/partner.order.status.put>
- partner.feedback.post: <https://yandex.ru/dev/eda-vendor/doc/ru/ref/Otzyvy/partner.feedback.post>
