FROM python:3.11-slim

# the same numpy, scipy and pandas as the agent's environment, for the program under test
RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

# parent of the declared artifact, /app/output/audit.py, which harbor uploads here
RUN mkdir -p /app/output

COPY . /tests/

# the agent's /app/data (documents and the example case), at the same path and read-only, so that a program that
# reads it at run time behaves as it did in the agent's environment
RUN mkdir -p /app/data && cp -r /tests/app_data/. /app/data/ && chown -R root:root /app/data \
    && chmod -R a+rX,go-w /app/data \
    && chmod +x /tests/test.sh \
    && chmod 700 /tests \
    && mkdir -p /logs/verifier \
    && chmod 700 /logs/verifier

WORKDIR /tests
ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=2
