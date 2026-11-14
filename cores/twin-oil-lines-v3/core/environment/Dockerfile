FROM python:3.11-slim

# The room in which /app/output/lines.py is written.
#
#   /app/data/docs       TS-2 and the description of a site package
#   /app/data/examples   two site packages, each with expected.csv, its results to TS-2
#   /app/data/pending    one site package that has not been calculated
#   /app/output          the only place the account agent can write under /app
#
# The survey crew is the account surveyor. What a survey of each pipe of the two example sites reads today
# is in its books under /opt/surveyors/sealed, which no other account can open; `heatsurvey` hands an order
# to /opt/surveyors/lab.py through sudo, and that program is the crew's whole rule. The crew has no book
# for the pending site.

ENV PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends sudo \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3

RUN useradd --create-home --user-group --shell /bin/bash agent \
    && useradd --system --user-group --no-create-home --shell /usr/sbin/nologin surveyor

COPY rig/lab.py /opt/surveyors/lab.py
COPY rig/sealed/ /opt/surveyors/sealed/
COPY rig/heatsurvey /usr/local/bin/heatsurvey
COPY rig/sudoers /etc/sudoers.d/surveyor
RUN chown root:root /opt/surveyors /opt/surveyors/lab.py /usr/local/bin/heatsurvey /etc/sudoers.d/surveyor \
    && chmod 755 /opt/surveyors /opt/surveyors/lab.py /usr/local/bin/heatsurvey \
    && chmod 440 /etc/sudoers.d/surveyor \
    && visudo -cf /etc/sudoers.d/surveyor \
    && chown -R surveyor:surveyor /opt/surveyors/sealed \
    && chmod 700 /opt/surveyors/sealed \
    && chmod 600 /opt/surveyors/sealed/*.json \
    && install -d -o surveyor -g surveyor -m 700 /opt/surveyors/state

COPY data/ /app/data/
RUN chown -R root:root /app/data \
    && chmod -R u=rwX,go=rX /app/data \
    && install -d -o agent -g agent -m 755 /app/output
WORKDIR /app
