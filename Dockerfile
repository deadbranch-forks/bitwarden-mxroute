FROM python:3.11-alpine

WORKDIR /app

COPY server/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN apk add --no-cache curl

COPY server .

EXPOSE 6123

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:6123", "app:app"] 
