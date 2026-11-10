FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY . /tests/
RUN chmod +x /tests/test.sh && mkdir -p /logs/verifier /app

WORKDIR /tests
ENV PYTHONUNBUFFERED=1
