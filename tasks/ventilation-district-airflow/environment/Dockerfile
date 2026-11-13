FROM python:3.11-slim

# Where airflow.py gets written.
#
# Two accounts besides root. `agent` writes the program and owns /app/output. `crew` is the survey crew: it
# has no login shell, and it alone can open the books that say what a survey of each branch would read
# today. The only thing agent can do as crew is run /opt/crew/lab.py, through the pqsurvey command, so a
# reading is had by ordering it and in no other way. The crew holds books for the two districts under
# /app/data/examples. It has not been to the district under /app/data/pending.

RUN useradd --create-home --user-group --shell /bin/bash agent \
    && useradd --system --user-group --no-create-home --shell /usr/sbin/nologin crew

RUN apt-get update \
    && apt-get install -y --no-install-recommends sudo \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3

# One thread to BLAS and OpenMP, here and where a finished program is run and timed.
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1

# /app/data: docs (VS-4, the package format), examples (two packages with expected.csv), pending (one
# package, no results). Root's, read-only to the rest.
WORKDIR /app
COPY data/ /app/data/
RUN chown -R root:root /app/data \
    && chmod -R a=rX,u+w /app/data \
    && install -d -o agent -g agent -m 755 /app/output

# /opt/crew: lab.py is the crew's whole rule and anyone may read it; sealed/ are its books and state/ the
# orders it has taken, both closed to every account but crew.
COPY rig/lab.py /opt/crew/lab.py
COPY rig/sealed/ /opt/crew/sealed/
RUN chown root:root /opt/crew /opt/crew/lab.py \
    && chmod 755 /opt/crew /opt/crew/lab.py \
    && chown -R crew:crew /opt/crew/sealed \
    && chmod 700 /opt/crew/sealed \
    && chmod 600 /opt/crew/sealed/*.json \
    && install -d -o crew -g crew -m 700 /opt/crew/state

# pqsurvey, and the single sudo rule behind it (checked at build time).
COPY rig/pqsurvey /usr/local/bin/pqsurvey
COPY rig/sudoers /etc/sudoers.d/crew
RUN chown root:root /usr/local/bin/pqsurvey /etc/sudoers.d/crew \
    && chmod 755 /usr/local/bin/pqsurvey \
    && chmod 440 /etc/sudoers.d/crew \
    && visudo -cf /etc/sudoers.d/crew
