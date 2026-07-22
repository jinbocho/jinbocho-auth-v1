FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

# Shell form: ${PORT} is injected by Render (falls back to 8001 locally).
# Migrations run on start so the DB schema is current before serving requests.
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001} --workers 2
