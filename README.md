# Card bot: бот на вашем ПК + Mini App на GitHub Pages

    bot.py                бот (aiogram) + API (aiohttp) + БД (aiosqlite), запускается у вас на ПК
    docs/index.html       Mini App, публикуется на GitHub Pages
    docs/cards/           картинки карточек: их же читает бот, их же отдаёт Pages
    make_placeholders.py  генератор тестовых картинок
    .env                  токен и адреса (в git не попадает)

## 1. Фронтенд на GitHub Pages
1. Создайте ПУБЛИЧНЫЙ репозиторий на GitHub и загрузите в него весь проект
   (`.env` и `bot.db` игнорируются через .gitignore, токен в репозиторий не попадёт).
2. Settings → Pages → Source: "Deploy from a branch", ветка main, папка /docs → Save.
3. Через 1–2 минуты сайт откроется по адресу https://<ник>.github.io/<репозиторий>/
   Это и есть WEBAPP_URL.

## 2. Бот на ПК
1. Python 3.10+: `python -m venv .venv`, активировать, `pip install -r requirements.txt`
2. Токен у @BotFather (/newbot).
3. Установите cloudflared: Windows `winget install Cloudflare.cloudflared`, macOS `brew install cloudflared`,
   Linux: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
4. `cp .env.example .env`, впишите BOT_TOKEN и WEBAPP_URL. API_URL оставьте пустым.
5. `python bot.py`. Бот сам запустит туннель к вашему ПК и передаст его адрес в Mini App.
6. В Telegram: /start, /free, затем кнопка «Моя коллекция».

## Важно
- Пока `bot.py` не запущен, Mini App пустой: данные лежат в bot.db на вашем ПК.
- При каждом запуске адрес туннеля новый. Кнопка меню обновляется сама, а кнопки под СТАРЫМИ сообщениями
  ведут на старый адрес: открывайте коллекцию через /collection или кнопку меню.
- Изменили docs/index.html или картинки: `git push`, Pages обновится за пару минут
  (Telegram может кэшировать страницу, тогда закройте и откройте Mini App снова).
