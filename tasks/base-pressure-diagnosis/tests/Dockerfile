FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

# parent of the declared artifact, /app/output/diagnosis.csv, which the harness copies here
RUN mkdir -p /app/output

COPY . /tests/

# the sealed fleet stays under /tests (700); the grader needs nothing from the agent's /app/data
RUN chmod +x /tests/test.sh \
    && chmod -R go-rwx /tests \
    && chmod 700 /tests \
    && mkdir -p /logs/verifier \
    && chmod 700 /logs/verifier

WORKDIR /tests
ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=2
