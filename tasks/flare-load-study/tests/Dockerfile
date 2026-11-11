FROM python:3.11-slim

# Harbor uploads the declared artifact into /app/output, so that directory has to exist in the image before
# the upload is attempted. Nothing later in this file touches it.
RUN mkdir -p /app/output

# The arithmetic of a graded run must not move between runs, so every package the grader can reach is pinned.
RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY . /tests/

# Three things live in /tests that the agent's image does not have: the sealed definition of unit 400, the
# grader that reads a submitted study against it, and the single pytest test that settles the reward. The
# first of those is why the whole directory is closed to everyone but root; test.sh is the only thing in it
# meant to be run.
RUN set -eu; \
    chown -R root:root /tests; \
    chmod +x /tests/test.sh; \
    chmod -R go-rwx /tests; \
    chmod 700 /tests

# A copy of the records the agent worked from, at the path they had in its container. They are kept for the
# record only: the grader reads the sealed definition and never these.
RUN set -eu; \
    mkdir -p /app/data; \
    cp -r /tests/app_data/. /app/data/; \
    chown -R root:root /app/data; \
    chmod -R a+rX,go-w /app/data

# pytest's report and the reward byte are written under /logs/verifier, which no one but root may open.
RUN set -eu; \
    mkdir -p /logs/verifier; \
    chown -R root:root /logs/verifier; \
    chmod 700 /logs/verifier

WORKDIR /tests
ENV PYTHONUNBUFFERED=1
# A compiled copy of the sealed definition would outlive the run that wrote it, so no bytecode is written.
ENV PYTHONDONTWRITEBYTECODE=1
ENV OMP_NUM_THREADS=2
