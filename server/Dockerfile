FROM python:3.11-alpine

WORKDIR /app

COPY server/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY server .

EXPOSE 6123

CMD ["gunicorn", "-w", "1" "-b" "--host=0.0.0.0:6123", "app:app"] 
