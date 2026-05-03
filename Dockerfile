FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./app.py
COPY positives ./positives
COPY public ./public

EXPOSE 8080

CMD ["sh", "-c", "python -c 'from app import init_db; init_db()' && exec gunicorn --bind 0.0.0.0:8080 --workers 2 app:app"]
