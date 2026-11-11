# The verifier image. It carries three things the agent's image does not: the sealed definition of unit 400, the
# grader that reads a submitted finding sheet against it, and the one pytest test that settles the reward.
FROM python:3.11-slim

# /app/output is where harbor uploads the declared artifact, /app/output/relief.csv. It has to exist before the
# upload, so it is made in a layer of its own and nothing later touches it.
RUN mkdir -p /app/output

# Pinned, so that a graded run is reproducible and the grader's arithmetic cannot move under it.
RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY . /tests/

# The agent's own records, at the path they had in its container, readable and not writable. They are here for
# the record: the grader reads the sealed definition, never these.
RUN set -eu; \
    mkdir -p /app/data; \
    cp -r /tests/app_data/. /app/data/; \
    chown -R root:root /app/data; \
    chmod -R a+rX,go-w /app/data

# /tests holds the sealed definition of unit 400, so nothing but root may look inside it. test.sh is the only
# thing in there meant to be run.
RUN set -eu; \
    chown -R root:root /tests; \
    chmod +x /tests/test.sh; \
    chmod -R go-rwx /tests; \
    chmod 700 /tests

# The reward and pytest's report are written here, and only root may read them.
RUN set -eu; \
    mkdir -p /logs/verifier; \
    chown -R root:root /logs/verifier; \
    chmod 700 /logs/verifier

WORKDIR /tests
ENV PYTHONUNBUFFERED=1
# No bytecode anywhere: a compiled copy of the sealed definition would outlive the run that made it.
ENV PYTHONDONTWRITEBYTECODE=1
ENV OMP_NUM_THREADS=2
