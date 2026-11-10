FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

RUN apt-get update && apt-get install -y --no-install-recommends sudo && rm -rf /var/lib/apt/lists/*

# Two users. The agent ([agent] user in task.toml) works in /app and writes only to /app/output. The rig runs as
# "rig": it alone can read the sealed definition and its own trial records. /opt/rig itself is root's, so neither
# user can rename or replace it.
RUN useradd --create-home --shell /bin/bash agent \
    && useradd --create-home --shell /usr/sbin/nologin rig

WORKDIR /app
COPY data/ /app/data/
RUN chown -R root:root /app/data && chmod -R a+rX,go-w /app/data \
    && chown root:root /app && chmod 755 /app \
    && mkdir -p /app/output && chown agent:agent /app/output

COPY rig/trial.py /opt/rig/trial.py
COPY rig/sealed/ /opt/rig/sealed/
RUN mkdir -p /opt/rig/state \
    && chown root:root /opt/rig /opt/rig/trial.py && chmod 755 /opt/rig && chmod 755 /opt/rig/trial.py \
    && chown -R rig:rig /opt/rig/sealed /opt/rig/state \
    && chmod 700 /opt/rig/sealed /opt/rig/state && chmod 600 /opt/rig/sealed/*

# the only privileged command: the agent may run the rig program as rig, non-interactively, with no environment
RUN printf 'Defaults!/opt/rig/trial.py env_reset,!env_keep\nagent ALL=(rig) NOPASSWD: /opt/rig/trial.py\n' \
      > /etc/sudoers.d/rig \
    && chmod 440 /etc/sudoers.d/rig && visudo -cf /etc/sudoers.d/rig
RUN printf '#!/bin/bash\nexec sudo -n -u rig /opt/rig/trial.py "$@"\n' > /usr/local/bin/trial \
    && chmod 755 /usr/local/bin/trial

ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV PYTHONUNBUFFERED=1
