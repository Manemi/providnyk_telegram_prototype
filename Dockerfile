FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system --gid 10001 providnyk \
    && adduser --system --uid 10001 --ingroup providnyk --home /home/providnyk providnyk

COPY requirements.txt requirements.lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements.lock.txt

COPY bot.py ./
COPY game ./game
COPY content ./content
COPY assets ./assets
COPY docs ./docs
COPY scripts ./scripts

RUN mkdir -p /app/data \
    && chown -R providnyk:providnyk /app

USER providnyk

VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os; os.kill(1, 0)"]

CMD ["python", "bot.py"]
