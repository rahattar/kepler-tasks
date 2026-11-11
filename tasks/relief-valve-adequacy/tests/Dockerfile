FROM python:3.11-slim

COPY requirements.txt /tests/requirements.txt
RUN pip install --no-cache-dir -r /tests/requirements.txt

COPY . /tests/

# /app/output is where the declared artifact arrives. /app/data carries the agent's own records at the same path,
# read-only, for the record. /tests holds the sealed definition, so it belongs to root alone.
RUN set -eu; \
    mkdir -p /app/output /app/data /logs/verifier; \
    cp -r /tests/app_data/. /app/data/; \
    chown -R root:root /app/data /tests /logs/verifier; \
    chmod -R a+rX,go-w /app/data; \
    chmod +x /tests/test.sh; \
    chmod -R go-rwx /tests; \
    chmod 700 /tests /logs/verifier

WORKDIR /tests
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=2
