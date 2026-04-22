FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.txt ./requirements.txt
COPY backend/requirements-ml.txt ./requirements-ml.txt
RUN pip install --no-cache-dir -r requirements-ml.txt

COPY backend/app ./app
COPY backend/start.sh ./start.sh
COPY backend/.env.example ./.env
COPY data ./data
RUN chmod +x ./start.sh

EXPOSE 8000

CMD ["./start.sh"]
