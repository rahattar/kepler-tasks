FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

RUN apt-get update && apt-get install -y --no-install-recommends sudo && rm -rf /var/lib/apt/lists/*

# Two users. The agent ([agent] user in task.toml) works in /app and writes only to /app/output. The laboratory runs
# as "lab": it alone can read the sealed definition and its own slot records, and it writes the test reports to
# /app/lab_reports, which the agent can read. /opt/lab itself is root's, so neither user can rename or replace it.
RUN useradd --create-home --shell /bin/bash agent \
    && useradd --create-home --shell /usr/sbin/nologin lab

WORKDIR /app
COPY data/ /app/data/
RUN chown -R root:root /app/data && chmod -R a+rX,go-w /app/data \
    && chown root:root /app && chmod 755 /app \
    && mkdir -p /app/output && chown agent:agent /app/output \
    && mkdir -p /app/lab_reports && chown lab:lab /app/lab_reports && chmod 755 /app/lab_reports

COPY rig/fcgr.py /opt/lab/fcgr.py
COPY rig/sealed/ /opt/lab/sealed/
RUN mkdir -p /opt/lab/state \
    && chown root:root /opt/lab /opt/lab/fcgr.py && chmod 755 /opt/lab && chmod 755 /opt/lab/fcgr.py \
    && chown -R lab:lab /opt/lab/sealed /opt/lab/state \
    && chmod 700 /opt/lab/sealed /opt/lab/state && chmod 600 /opt/lab/sealed/*

# the only privileged command: the agent may run the laboratory program as lab, non-interactively, with no environment
RUN printf 'Defaults!/opt/lab/fcgr.py env_reset,!env_keep\nagent ALL=(lab) NOPASSWD: /opt/lab/fcgr.py\n' \
      > /etc/sudoers.d/lab \
    && chmod 440 /etc/sudoers.d/lab && visudo -cf /etc/sudoers.d/lab
RUN printf '#!/bin/bash\nexec sudo -n -u lab /opt/lab/fcgr.py "$@"\n' > /usr/local/bin/fcgr \
    && chmod 755 /usr/local/bin/fcgr

ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV PYTHONUNBUFFERED=1
