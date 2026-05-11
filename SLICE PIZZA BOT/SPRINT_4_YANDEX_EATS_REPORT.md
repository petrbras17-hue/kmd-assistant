# Sprint 4 — Yandex Eats Partner API Integration Report

**Дата:** 2026-05-12
**Бренд:** Миа пицца на Княжьем озере (place_id=286411)
**ИНН:** 770306478430 | Договор № 62283600/26 от 28.04.2026
**Partner UUID:** `c92dba08-a723-4b14-80f4-f64d76f686c4`

## TL;DR

Полная интеграция с официальным Yandex Eats Partner API готова. Код запускается,
тесты зелёные. **Не хватает только `client_id` / `client_secret`**, которые
должен взять Пётр из кабинета (см. раздел «Что от Пётра нужно»).

## Что подключено

### 1. Async OAuth-клиент: `slice_pizza_bot/services/yandex_eats_vendor.py`

Реализованы методы:

| Метод | Назначение |
| --- | --- |
| `get_token()` | OAuth Client Credentials → access_token (с in-memory кэшем + refresh) |
| `get_menu()` | `GET /menu/{place_id}/composition` — текущее меню |
| `get_availability()` | `GET /menu/{place_id}/availability` — стоп-лист |
| `update_menu(composition)` | `POST /menu/import/initiation` — заливка меню |
| `get_orders(date_from, status)` | `POST /partner/orders/history` |
| `get_order_details(order_ids)` | `POST /partner/integration/v1/get-orders-details` |
| `update_order_status(order_id, status)` | `PUT /order/{id}/status` |
| `stoplist_add(item_id, until)` | Добавить в стоп-лист (идемпотентно) |
| `stoplist_remove(item_id)` | Убрать из стоп-листа |
| `get_reviews()` | Pull отзывов (опытный endpoint, fallback на cookie-сессию) |
| `reply_to_review(id, text, promo_discount)` | `POST /feedback-answer` |
| `block_restaurant(from, to, reason)` | `POST /block` |
| `unblock_restaurant(block_ids)` | `POST /unblock` |
| `block_status()` | `POST /v2/status` |

Особенности:
- Retry 3 раза с экспо-бэкоффом (1/2/4s) на 5xx и сетевые ошибки.
- Автоматический refresh OAuth токена на 401 + повторная попытка.
- Respect `Retry-After` на 429.
- `Idempotency-Key` для всех write-операций (защита от дублей).
- Маскированное логирование (никогда не печатается `client_secret` / `access_token`).

### 2. Webhook receiver: `POST /webhook/yandex-eats`

`slice_pizza_bot/webapp/api.py`:

- Принимает события `order.created`, `order.status_changed`, `order.cancelled`,
  `feedback.created`. Также понимает push-формат без `event_type` (по наличию
  `eatsId` / `items`).
- Аутентификация — shared-secret `X-Yandex-Auth-Token` (`hmac.compare_digest`).
- Идемпотентность через таблицу `webhook_events` (UNIQUE source+event_id).
- На `order.created`:
  1. Парсит payload через `parse_yandex_eats_order(...)`.
  2. Дедупликация по `yandex_eats_order_id`.
  3. Создаёт `order` с `source='yandex_eats'` через `db.create_order(...)`.
  4. Шлёт в кухонный Telegram-чат через `services.kitchen.send_order_to_kitchen`.
- На `order.status_changed`: маппит `CANCELLED`/`TAKEN_BY_COURIER`/`DELIVERED` →
  `отменён`/`в пути`/`доставлен` и обновляет локальный order.
- На `feedback.created`: пишет в `yandex_eats_reviews`, шлёт админу alert при rating ≤ 3.

### 3. Auto-sync меню: `scripts/sync_yandex_menu.py`

```bash
python scripts/sync_yandex_menu.py --dry-run     # показать diff
python scripts/sync_yandex_menu.py               # отправить меню в Я.Еду
```

- Source-of-truth — `menu.json` в репозитории.
- Исключает «Чоризо неаполитанская» и «Карамельный лук».
- Цена для Я.Еды: `base_price × 1.46`, округлено до 10₽
  (Маргарита 540₽ → 790₽).
- Diff показывает added / removed / price changes.
- Safe-by-default: даже при `--dry-run=false`, если `YANDEX_EATS_ENABLED=False`
  — выходит с кодом 3 без записи.

### 4. Auto-stoplist sync: hook в `services/inventory.py`

`InventoryService.deduct_ingredients()` после списания и до возврата вызывает
`_auto_push_yandex_stoplist(order_items)`. Логика:
- Если ингредиент опустился до нуля → определяем затронутые `menu_item_id` →
  ищем `yandex_eats_item_id` в таблице `dishes` → `stoplist_add(yid)`.
- Не падает если Я.Еда недоступна (best-effort).

### 5. Auto-reviews reply: `services/yandex_eats_reviews.py`

`run_auto_reply_pass()` — функция для cron'а каждые 6 часов:
- Берёт неотвеченные отзывы из `yandex_eats_reviews` со `status='received'`.
- rating ≥ 4 → генерирует ответ через Anthropic (через прокси `ANTHROPIC_BASE_URL`)
  → `reply_to_review`.
- rating ≤ 3 → НЕ автоотвечаем, шлём админу в Telegram через `alert_admin`.
- Правила: без эмодзи, без извинений за рецепт, до 300 символов.

### 6. Миграция БД: `alembic/versions/20260512_14_yandex_eats_partner.py`

Новые поля и таблицы:
- `orders.source` (default `'bot'`, новое значение — `'yandex_eats'`)
- `orders.yandex_eats_order_id` (UNIQUE индекс — защита от дублей webhook'а)
- `orders.external_payload` (JSON snapshot push'а для аудита)
- `dishes.yandex_eats_price_kopecks` — наценка для Я.Еды (опционально)
- `dishes.yandex_eats_item_id` — внешний id в каталоге Я.Еды
- `dishes.yandex_eats_in_stoplist` — bitfield
- `yandex_eats_reviews` — таблица отзывов с auto-reply статусами

Применить: `./venv/bin/alembic upgrade head` (head = `20260512_14`).

### 7. Конфигурация: `config.py`

Добавлены поля в `Settings`:
- `YANDEX_EATS_CLIENT_ID`
- `YANDEX_EATS_CLIENT_SECRET`
- `YANDEX_EATS_OAUTH_URL` (default `https://vendor.eda.yandex.net`)
- `YANDEX_EATS_API_URL` (default `https://api.eda.yandex.ru`)
- `YANDEX_EATS_WEBHOOK_TOKEN` (shared-secret для входящих webhook'ов)
- `YANDEX_EATS_ENABLED` (фича-флаг)
- `YANDEX_EATS_PARTNER_UUID` (default уже зашит на наш UUID)
- `YANDEX_EATS_PLACE_ID` (default `'286411'`)

### 8. Документация

- `YANDEX_EATS_API_FULL_DOCS.md` — полная сводка всех endpoint'ов, OAuth-флоу,
  curl-примеров и точного пути для получения `client_id` в кабинете.

### 9. Тесты

`tests/test_yandex_eats_vendor.py` — 14 тестов, все зелёные:
- pure helpers (mask, _escape_review_text, parse_yandex_eats_order)
- OAuth: кэширование, force_refresh, NotConfigured
- get_menu / get_orders / stoplist_add / update_order_status / reply_to_review
- 401 → token refresh + retry

Запуск: `./venv/bin/python -m pytest tests/test_yandex_eats_vendor.py -q`.

## Что от Пётра нужно для активации

### 1. Получить `client_id` и `client_secret`

**Точный путь в кабинете** `https://vendor.eda.yandex/home`:

1. Войти под `pete.braslavskii@yandex.ru`.
2. В левой панели выбрать ресторан **«Миа пицца на Княжьем озере»**.
3. Нажать шестерёнку **«Настройки»** (Settings) внизу левой панели.
4. Перейти в раздел **«Интеграции»** или **«API»** (название может варьироваться;
   ищите блок с упоминанием «Партнёрское API» / «Vendor Management Integration»).
5. Нажать **«Создать ключи»** или **«Сгенерировать»** — появятся `client_id`
   (виден сразу) и `client_secret` (виден один раз, нажать **«Показать»** /
   **«Скопировать»**).

Если на шаге 4 ничего не нашлось:
- **Альтернатива A:** в правом верхнем углу нажать аватар →
  **«Профиль партнёра»** → **«Доступы для разработчиков»**.
- **Альтернатива B:** на странице **«Интеграция с POS / iiko»** прокрутить
  вниз — блок **«Прямая интеграция API»** с client_id/secret.
- **Альтернатива C:** в разделе **«Документация партнёра»** ссылка
  **«Запросить API-доступ»** → client_id виден в модалке, secret приходит
  на email `pete.braslavskii@yandex.ru`.

### 2. Прислать ключи через зашифрованный канал

В `.env` на VPS `158.160.227.3`:
```
YANDEX_EATS_CLIENT_ID=<скопированное значение>
YANDEX_EATS_CLIENT_SECRET=<скопированное значение>
YANDEX_EATS_WEBHOOK_TOKEN=<сгенерируем сами, 32+ символа>
YANDEX_EATS_ENABLED=true
```

### 3. Зарегистрировать webhook URL в кабинете Я.Еды

В разделе **«Webhooks»** или **«Callbacks»** кабинета указать:
```
URL: https://api.slicepizza.ru/webhook/yandex-eats
Methods: POST, PUT
Auth header: X-Yandex-Auth-Token (значение из YANDEX_EATS_WEBHOOK_TOKEN)
Events: order.created, order.status_changed, order.cancelled, feedback.created
```

### 4. Прогнать миграцию + dry-run меню

```bash
ssh yc-user@158.160.227.3
cd /opt/slice_pizza_bot
./venv/bin/alembic upgrade head           # применить миграцию 14
./venv/bin/python scripts/sync_yandex_menu.py --dry-run  # увидеть diff
./venv/bin/python scripts/sync_yandex_menu.py            # залить меню
```

## 3 главных эффекта от Sprint 4 для Пётра

1. **Заказы из Я.Еды автоматически попадают на кухню.** Каждый push от Yandex Eats
   создаёт `order` в нашей БД, мгновенно отправляется звуковое уведомление в
   Telegram-чат кухни `-5031424054`. Кухня видит заказ за секунды, без ручного
   копирования из мобильного приложения вендора.

2. **Меню — один source of truth.** `menu.json` в нашем репо = что показывается
   в Telegram mini-app, на сайте, и в Я.Еде. Скрипт `sync_yandex_menu.py`
   синхронизирует с автоматической наценкой 1.46× (компенсация комиссии 30.81%).
   Чоризо неаполитанская и Карамельный лук исключаются из push'а программно.

3. **Стоп-лист и отзывы — автоматически.** Когда ингредиент кончается,
   `inventory.deduct_ingredients` пушит блюдо в стоп-лист Я.Еды. Положительные
   отзывы (rating ≥ 4) получают AI-сгенерированный ответ через Anthropic
   (с соблюдением правил без извинений за рецепт). Негатив попадает в Telegram
   админа для ручного ответа — никаких ботовых отписок на критику.

## Acceptance checklist

- [x] Партнёрский UUID и place_id в `config.py`
- [x] `YandexEatsVendor` async-клиент c OAuth + retry + idempotency
- [x] Webhook `/webhook/yandex-eats` с auth + dedup + kitchen-notify
- [x] Авто-sync меню (`scripts/sync_yandex_menu.py --dry-run`)
- [x] Авто-stoplist в `services/inventory.py`
- [x] Авто-reply на положительные отзывы через Anthropic (через прокси!)
- [x] Алерт в Telegram админу на негативные отзывы
- [x] Alembic миграция `20260512_14`
- [x] Тесты: 14 шт., все зелёные
- [x] Документация: `YANDEX_EATS_API_FULL_DOCS.md`
- [ ] Пётр прислал `client_id`/`client_secret` (блокер активации)
- [ ] Webhook URL зарегистрирован в кабинете
- [ ] Production smoke test (после получения ключей)
