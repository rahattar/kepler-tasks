FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

# parent of the declared artifact, /app/output/damage.json, which harbor uploads here
RUN mkdir -p /app/output

COPY . /tests/

RUN chmod +x /tests/test.sh \
    && chmod 700 /tests \
    && mkdir -p /logs/verifier \
    && chmod 700 /logs/verifier

WORKDIR /tests
ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=2
