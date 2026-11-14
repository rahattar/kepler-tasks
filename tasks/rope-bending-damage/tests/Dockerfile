# Image the verifier runs in. Nothing from the agent's container is in it but /app/output/ropes.py, which is
# put in place before tests/test.sh starts; the network is off.
#   /tests          test.sh; test_ropes.py, pytest's one test; rope_bench.py, which runs the program and reads
#                   pytest's report; works/, the six packages; sealed/results/, their damages
#   /logs/verifier  reward.txt, the ctrf report, the bench's notes
FROM python:3.11-slim

# The libraries the program may import, then pytest and its ctrf reporter.
RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3 pytest==8.4.1 pytest-json-ctrf==0.3.5

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

COPY . /tests/
RUN chown -R root:root /tests && chmod -R go-rwx /tests && chmod 0700 /tests/test.sh

RUN mkdir -p /app/output
RUN mkdir -p /logs/verifier && chmod 0700 /logs/verifier

# The program becomes nobody through setpriv, from util-linux in the base image; stop here if that is gone.
RUN setpriv --reuid 65534 --regid 65534 --clear-groups true

WORKDIR /tests
