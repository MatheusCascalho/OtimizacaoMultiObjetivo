FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY migrations ./migrations
COPY alembic.ini .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "api:create_app()"]
