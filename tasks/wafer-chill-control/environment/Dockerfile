FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

WORKDIR /app
RUN mkdir -p /app /data

COPY data/ /data/
COPY check_controller.py /app/check_controller.py
RUN chmod +x /app/check_controller.py

ENV PYTHONUNBUFFERED=1
