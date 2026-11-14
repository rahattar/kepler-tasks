# Where a delivered ropes.py is tried. Built without the agent's files; run without a network.
#
#   /app/output/ropes.py   the program, put here before test.sh is started
#   /tests                 test.sh, the one pytest test (test_ropes.py), the bench that runs the program
#                          (rope_bench.py), the reader of pytest's report (tally.py), the six works (works/)
#                          and their sealed damages (sealed/results/)
#   /logs/verifier         reward.txt, pytest's report, the bench's notes
#
# test.sh is root. The bench starts the program as nobody, for whom /tests and /logs/verifier are closed.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

# What the program may import, then what the test needs.
RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3 \
 && pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

# setpriv is how the bench becomes nobody; it comes with the base image, and the build stops here if it has gone.
RUN setpriv --reuid 65534 --regid 65534 --clear-groups true

RUN mkdir -p /app/output
RUN mkdir -p /logs/verifier && chmod 0700 /logs/verifier

WORKDIR /tests
COPY . /tests/
RUN chown -R root:root /tests && chmod -R go-rwx /tests && chmod 0700 /tests/test.sh
