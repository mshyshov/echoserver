FROM python:3.11-slim

WORKDIR /app

COPY main.py .

EXPOSE 8080

CMD ["python3", "main.py", "--host", "0.0.0.0", "--port", "8080"]
