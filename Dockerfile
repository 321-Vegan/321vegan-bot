FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system bot && adduser --system --ingroup bot bot

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --disable-pip-version-check .

USER bot

STOPSIGNAL SIGTERM

CMD ["python", "-m", "vegan_discord_bot"]
