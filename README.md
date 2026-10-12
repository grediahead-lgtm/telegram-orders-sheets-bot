# telegram-orders-sheets-bot

A small Telegram bot that takes a simple order step by step (item, quantity, contact, comment, optional photo) and saves it as a row in a **CSV file** or a **Google Sheet**. Python standard library only.

## What it does
- `/order` starts the dialog, `/cancel` stops it, `/start` shows help. Private chats only; other bots are ignored.
- Each answer is checked: quantity must be a whole number from 1 to 9999; texts are trimmed to 500 characters.
- If saving fails (for example Google is unreachable) the customer's answers are kept and they can retry; nothing is lost silently.
- Optional notification to the owner's chat for each saved order.
- Rate limit per chat (20 messages a minute). Spreadsheet formula injection is blocked: a value starting with `=`, `+`, `-` or `@` is stored with a leading `'`.
- The bot token and the webhook secret come from environment variables, never from the config or logs. Message texts are not logged.

## Quick start (CSV)
```bash
cp examples/config.example.json config.json    # edit the texts
PYTHONPATH=src python3 -m order_bot --config config.json --check
TELEGRAM_BOT_TOKEN=123456:your-token PYTHONPATH=src python3 -m order_bot --config config.json
```
Orders are appended to `orders.csv` (header written once).

## Google Sheets without OAuth
The bot sends each order as JSON to a small Google Apps Script web app that appends a row to your sheet:
1. Open your Sheet > Extensions > Apps Script, paste `apps_script/Code.gs`.
2. Project settings > Script properties: add `ORDER_SECRET` (a long random string).
3. Deploy > New deployment > Web app (Execute as: Me; access: Anyone). Copy the `/exec` URL.
4. In `config.json` set `"storage": "webhook"` and `webhook_url`. Start the bot with `ORDER_WEBHOOK_SECRET` set to the same string.

## Tests
`python3 -m unittest discover -s tests` (no internet, no real token; the webhook is tested against a local server).

## Limits (read this)
- The Python side is covered by automated tests. **`apps_script/Code.gs` is not tested against a live Google account** in this repository: deploy it on a test sheet first.
- Not a shop: no payments, no stock, no prices. Dialog state is kept in memory, so a restart cancels unfinished orders.
- Long polling from your own computer or server; put it under a process manager for production.
- Anyone who knows the web-app URL can call it, so the secret matters. Do not commit your `config.json` with real URLs.

MIT license.

---

# telegram-orders-sheets-bot (українською)

Невеликий Telegram-бот, який крок за кроком приймає просте замовлення (товар, кількість, контакт, коментар, фото за бажанням) і записує його рядком у **CSV** або **Google Таблицю**. Лише стандартна бібліотека Python.

**Швидкий старт:** скопіюйте `examples/config.example.json` у `config.json`, відредагуйте тексти, перевірте (`--check`) і запустіть з `TELEGRAM_BOT_TOKEN`. Для Google Таблиці вставте `apps_script/Code.gs` у Apps Script, задайте `ORDER_SECRET`, опублікуйте як веб-застосунок і вкажіть `webhook_url`.

**Важливо:** Python-частину перевірено тестами; скрипт `Code.gs` не перевірявся на живому акаунті Google. Це приймання заявок, а не магазин: без оплат і складу.
