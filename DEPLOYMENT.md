# Розгортання «Провідник: Контур» на окремому сервері

## Критично перед запуском

Початковий ZIP містив реальний `TELEGRAM_BOT_TOKEN` і `OPENAI_API_KEY`. Вважай обидва ключі скомпрометованими:

1. Перегенеруй токен бота в `@BotFather`.
2. Відклич старий OpenAI API key у кабінеті OpenAI та створи новий.
3. Не завантажуй початковий ZIP на сервер, у GitHub або в хмарне сховище.
4. Використовуй підготовлений очищений архів, у якому немає `.env`, локальної БД і macOS-venv.

## Що потрібно

- VPS з Ubuntu 24.04 LTS або іншим сучасним Linux.
- Для старту достатньо 1 vCPU, 1 GB RAM і 10 GB SSD.
- Docker Engine із Compose plugin.
- Відкритий вихідний HTTPS-доступ. Вхідні порти для long polling не потрібні.

Актуальна офіційна інструкція встановлення: [Docker Engine для Ubuntu](https://docs.docker.com/engine/install/ubuntu/) і [Compose plugin](https://docs.docker.com/compose/install/linux/).

Бот працює через Telegram long polling, тому домен, Nginx і TLS-сертифікат для першого релізу не потрібні.

## Рекомендований варіант: Docker Compose

### 1. Створи користувача й каталог

```bash
sudo adduser --disabled-password --gecos "" providnyk
sudo mkdir -p /opt/providnyk
sudo chown providnyk:providnyk /opt/providnyk
```

### 2. Передай очищений архів на сервер

На Mac:

```bash
scp providnyk_server_ready.zip providnyk@SERVER_IP:/opt/providnyk/
```

На сервері:

```bash
cd /opt/providnyk
unzip providnyk_server_ready.zip
cd providnyk_telegram_prototype
```

### 3. Створи секретну конфігурацію

```bash
cp .env.example .env
nano .env
chmod 600 .env
```

Обов’язково заповни:

```dotenv
TELEGRAM_BOT_TOKEN=новий_токен_від_BotFather
OPENAI_API_KEY=новий_openai_api_key
OPENAI_MODEL=gpt-5.5
ENABLE_AI_SCENES=true
```

Якщо хочеш спочатку перевірити гру без витрат OpenAI:

```dotenv
OPENAI_API_KEY=
ENABLE_AI_SCENES=false
```

У такому режимі бот використовує сценарні сцени з JSON.

### 4. Запусти

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f --tail=100 bot
```

У Telegram надішли боту:

```text
/newgame
```

### 5. Перевір

У логах мають з’явитися старт бота й шлях до БД без traceback:

```bash
docker compose logs --tail=100 bot
```

Перевір сценарій:

1. `/newgame`
2. Обери складність.
3. Обери характер.
4. Напиши `Оглянь номер`.
5. Відкрий `📒 Блокнот` і перевір появу доказів.

## Оновлення гри

Перед оновленням зроби backup, потім:

```bash
cd /opt/providnyk/providnyk_telegram_prototype
docker compose down
```

Заміни код, але не копіюй поверх нього чужий `.env` або стару БД. Потім:

```bash
docker compose up -d --build
docker compose logs -f --tail=100 bot
```

Не запускай два екземпляри цього бота одночасно з одним Telegram-токеном. Long polling розрахований на одну активну репліку.

## Резервна копія SQLite

Створи узгоджену копію всередині контейнера:

```bash
docker compose exec -T bot python scripts/backup_db.py /tmp/providnyk-backup.sqlite3
mkdir -p backups
docker compose cp bot:/tmp/providnyk-backup.sqlite3 ./backups/providnyk-$(date +%F-%H%M).sqlite3
```

Зберігай backup поза сервером:

```bash
scp providnyk@SERVER_IP:/opt/providnyk/providnyk_telegram_prototype/backups/*.sqlite3 ./
```

Для автоматизації додай серверний cron після того, як перевіриш команду вручну.

## Відновлення

Практичний спосіб із підключеним Docker volume:

```bash
docker compose up -d
docker compose cp ./backups/ПОТРІБНИЙ_BACKUP.sqlite3 bot:/app/data/restore.sqlite3
docker compose stop bot
docker compose run --rm --no-deps bot sh -c \
  'rm -f /app/data/providnyk.sqlite3 /app/data/providnyk.sqlite3-wal /app/data/providnyk.sqlite3-shm && mv /app/data/restore.sqlite3 /app/data/providnyk.sqlite3'
docker compose up -d
```

## Варіант без Docker: systemd

Файл сервісу лежить у `deploy/providnyk.service`.

```bash
sudo apt update
sudo apt install -y python3 python3-venv
sudo adduser --system --group --home /opt/providnyk providnyk
sudo mkdir -p /opt/providnyk /var/lib/providnyk /etc/providnyk
sudo chown -R providnyk:providnyk /opt/providnyk /var/lib/providnyk
```

Після копіювання проєкту:

```bash
sudo -u providnyk python3 -m venv /opt/providnyk/.venv
sudo -u providnyk /opt/providnyk/.venv/bin/pip install -r /opt/providnyk/requirements.lock.txt
sudo cp .env.example /etc/providnyk/providnyk.env
sudo nano /etc/providnyk/providnyk.env
sudo chmod 600 /etc/providnyk/providnyk.env
sudo chown root:root /etc/providnyk/providnyk.env
```

У systemd-конфігурації встанови:

```dotenv
GAME_DB_PATH=/var/lib/providnyk/providnyk.sqlite3
```

Потім:

```bash
sudo cp deploy/providnyk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now providnyk
sudo systemctl status providnyk
sudo journalctl -u providnyk -f
```

## Експлуатаційні правила

- Один Telegram-токен — один активний процес.
- `.env` ніколи не коміть у Git.
- Роби щоденний backup БД.
- Стеж за витратами OpenAI й установи billing limit.
- Для дешевшого AI-режиму можна перевірити `OPENAI_MODEL=gpt-5.4-mini`.
- Якщо аудиторія виросте до сотень одночасних гравців або потрібні кілька реплік, перенеси стан із SQLite у PostgreSQL і додай чергу/ліміти для AI-викликів.

## Типові проблеми

### `TelegramConflictError`

Десь уже працює інший процес із тим самим токеном. Зупини старий контейнер або локальний бот.

### Бот мовчить

```bash
docker compose ps
docker compose logs --tail=200 bot
```

Перевір токен, доступ сервера до `api.telegram.org` і чи не залишився старий webhook.

### AI-сцени не працюють, але гра відповідає

Це штатний fallback. Перевір `OPENAI_API_KEY`, `ENABLE_AI_SCENES`, модель і логи. При помилці OpenAI гра продовжує працювати на сценарних сценах.

### `database is locked`

Переконайся, що запущено лише один контейнер. Не відкривай робочу БД стороннім редактором. Для масштабування переходь на PostgreSQL.

## Перенесення старого прогресу

Окремо підготовлено файл `migration_data/providnyk_existing_state.sqlite3`. Він містить 1 профіль гравця та 25 записів журналу з початкового архіву. Цей файл навмисно не входить у server-ready ZIP, бо містить Telegram ID та приватний стан гри.

Щоб перенести його:

```bash
docker compose up -d
docker compose cp /ШЛЯХ/providnyk_existing_state.sqlite3 bot:/app/data/restore.sqlite3
docker compose stop bot
docker compose run --rm --no-deps bot sh -c \
  'rm -f /app/data/providnyk.sqlite3 /app/data/providnyk.sqlite3-wal /app/data/providnyk.sqlite3-shm && mv /app/data/restore.sqlite3 /app/data/providnyk.sqlite3'
docker compose up -d
```

Якщо старий прогрес не потрібен, нічого переносити не треба — бот створить чисту БД автоматично.
