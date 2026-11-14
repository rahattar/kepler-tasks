FROM python:3.11-slim

# The room in which a delivered lines.py is run again and compared. It has no network.
#
#   /app/output/lines.py   the delivery
#   /app/data              the documents and the three packages the program was written beside
#   /tests/sites           the six packages it is run on        /tests/results   their sealed results
#   /tests/crew            the survey crew: lab.py is its rule, books/ what a survey reads at each of the six
#   /logs/verifier         ctrf.json, sites.json and reward.txt
#
# rerun.py is root here. It starts the program as nobody, counts its time, and is the survey crew for the
# length of a run: the heatsurvey installed below leaves the program's order under /run/heat-desk and
# rerun.py answers it from books nobody cannot open.

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# One thread to BLAS and OpenMP, as in the room where the program was written. No CPU affinity is set.
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3
RUN pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

RUN mkdir -p /app/output
COPY . /tests/
WORKDIR /tests

RUN install -o 0 -g 0 -m 755 /tests/crew/heatsurvey /usr/local/bin/heatsurvey \
    && mkdir -p /app/data \
    && cp -r /tests/app_data/. /app/data/ \
    && chown -R 0:0 /app/data /tests \
    && chmod -R u=rwX,go=rX /app/data \
    && chmod -R u=rwX,go= /tests \
    && install -d -o 0 -g 0 -m 700 /logs/verifier
