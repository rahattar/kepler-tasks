FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl jq \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

WORKDIR /app
RUN mkdir -p /app /data

COPY data/ /data/
COPY bench.py /app/bench.py
RUN chmod +x /app/bench.py

ENV BENCH_URL=http://bench:8000
ENV PYTHONUNBUFFERED=1
