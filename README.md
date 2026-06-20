# Провідник: Контур

Telegram-прототип української детективно-шпигунської RPG-повісті.

Гравець керує Тарасом Сірком, обирає складність і характер героя, вільно описує дії, збирає докази, перевіряє версії та впливає на приховану пам’ять NPC.

## Як працює

- `bot.py` — Telegram-інтерфейс на aiogram.
- `game/engine.py` — ігровий цикл і відображення стану.
- `game/rules.py` — характеристики, навички, ризики та пам’ять NPC.
- `content/season_01_episode_01.json` — сюжет, сцени, локації й персонажі.
- `game/db.py` — збереження прогресу в SQLite.
- `game/llm.py` — необов’язкова генерація сцен через OpenAI Responses API.

Якщо OpenAI вимкнений або тимчасово недоступний, гра автоматично використовує сценарні сцени з JSON.

## Команди гри

- `/start` — почати або продовжити.
- `/newgame` — почати справу заново.
- `/profile` — характеристики Тараса.
- `/skills` — навички.
- `/mission` — картка місії.
- `/notebook` — докази й версії.
- `/map` — локація та напрямки.
- `/hint` — підказка згідно з режимом.
- `/evidence` — докази.
- `/suspects` — фігуранти.
- `/theory текст` — перевірити версію.
- `/journal` — останні події.
- `/help` — інструкція.

## Локальний запуск

Потрібен Python 3.13.

```bash
cp .env.example .env
nano .env
./run_local.sh
```

Мінімальна конфігурація:

```dotenv
TELEGRAM_BOT_TOKEN=токен_від_BotFather
OPENAI_API_KEY=
ENABLE_AI_SCENES=false
```

Для AI-сцен:

```dotenv
OPENAI_API_KEY=твій_ключ
OPENAI_MODEL=gpt-5.5
ENABLE_AI_SCENES=true
```

## Перевірка

```bash
python -m unittest discover -s tests -v
python -m compileall -q bot.py game
```

## Сервер

Готові файли:

- `Dockerfile`
- `compose.yaml`
- `deploy/providnyk.service`
- `DEPLOYMENT.md`
- `scripts/backup_db.py`

Повна покрокова інструкція: [DEPLOYMENT.md](DEPLOYMENT.md).

Архітектурний і продуктовий розбір: [ANALYSIS.md](ANALYSIS.md).

## Важливі обмеження

- Для Telegram long polling запускай лише одну репліку бота.
- SQLite підходить для одного сервера й раннього релізу.
- Для кількох реплік або високого навантаження потрібен PostgreSQL.
- `.env`, база даних, `venv` і кеші не мають потрапляти в Git чи релізний архів.

Усі персонажі прототипу вигадані. Вороги описуються як конкретні агенти, посередники, контрабандисти й корумповані фігуранти, а не як етнічні групи.
