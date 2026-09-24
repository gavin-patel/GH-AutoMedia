FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir flask pillow opencv-python-headless watchdog

EXPOSE 8080

CMD ["python", "app.py"]