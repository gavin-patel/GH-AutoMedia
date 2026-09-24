FROM python:3.12-slim

WORKDIR /app

ARG BUILD_REVISION=20260924
RUN echo "Building ${BUILD_REVISION}"

COPY . .

RUN pip install --no-cache-dir flask pillow opencv-python-headless watchdog pyftpdlib pyopenssl rawpy

EXPOSE 8080
EXPOSE 2121
EXPOSE 30000-30009

CMD ["python", "bootstrap.py"]