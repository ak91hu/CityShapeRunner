FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY data ./data
COPY scripts ./scripts

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python scripts/seed_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
