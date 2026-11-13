FROM python:3.11-slim

# Where a delivered airflow.py is run and compared. No network.
#
# Root is the checker and, for the length of each run, the survey crew: judge_airflow.py opens a socket,
# the pqsurvey installed below carries the program's order to it, and the answer is worked out by
# crew/lab.py from books under /tests that only root can read. The program itself runs as nobody.
#
#   /app/output/airflow.py    the delivery
#   /app/data                 what the program's author had, at the same path
#   /tests/districts          the six packages; /tests/results their sealed airflows; /tests/crew the crew
#   /logs/verifier            ctrf.json, districts.json, reward.txt

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# Timed with one thread to BLAS and OpenMP, as the program was written. Nothing here sets CPU affinity.
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1

RUN pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5
RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3

RUN mkdir -p /app/output
WORKDIR /tests
COPY . /tests/

# setpriv drops the program to nobody. It ships with the base image; stop the build if it ever does not.
RUN command -v setpriv

RUN install -m 755 /tests/crew/pqsurvey /usr/local/bin/pqsurvey

RUN install -d -m 755 /app/data \
    && cp -r /tests/app_data/. /app/data/ \
    && chown -R 0:0 /app/data \
    && chmod -R a=rX,u+w /app/data

# Districts, results, books and the checker are root's and nobody else's.
RUN chown -R 0:0 /tests \
    && chmod -R u=rwX,go= /tests \
    && chmod u+x /tests/test.sh \
    && install -d -m 700 -o 0 -g 0 /logs/verifier
