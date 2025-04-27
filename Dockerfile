FROM python:3.9-slim

RUN apt-get update && apt-get install -y     && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/data
WORKDIR /app

COPY . /app

RUN pip install flask

RUN chmod a+rwx /app/data

EXPOSE 8000

CMD ["python", "app.py"]
