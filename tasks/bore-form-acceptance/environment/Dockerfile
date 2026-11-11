FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

RUN apt-get update && apt-get install -y --no-install-recommends sudo && rm -rf /var/lib/apt/lists/*

# Two users. The agent ([agent] user in task.toml) works in /app and writes only to /app/output. The metrology room
# runs as "room": it alone can read the sealed definition and its own booking records, and it writes the scans to
# /app/scan_reports, which the agent can read. /opt/room itself is root's, so neither user can rename or replace it.
RUN useradd --create-home --shell /bin/bash agent \
    && useradd --create-home --shell /usr/sbin/nologin room

WORKDIR /app
COPY data/ /app/data/
RUN chown -R root:root /app/data && chmod -R a+rX,go-w /app/data \
    && chown root:root /app && chmod 755 /app \
    && mkdir -p /app/output && chown agent:agent /app/output \
    && mkdir -p /app/scan_reports && chown room:room /app/scan_reports && chmod 755 /app/scan_reports

COPY rig/lab.py /opt/room/lab.py
COPY rig/sealed/ /opt/room/sealed/
RUN mkdir -p /opt/room/state \
    && chown root:root /opt/room /opt/room/lab.py && chmod 755 /opt/room && chmod 755 /opt/room/lab.py \
    && chown -R room:room /opt/room/sealed /opt/room/state \
    && chmod 700 /opt/room/sealed /opt/room/state && chmod 600 /opt/room/sealed/*

# the only privileged command: the agent may run the metrology room's program as room, with no environment
RUN printf 'Defaults!/opt/room/lab.py env_reset,!env_keep\nagent ALL=(room) NOPASSWD: /opt/room/lab.py\n' \
      > /etc/sudoers.d/room \
    && chmod 440 /etc/sudoers.d/room && visudo -cf /etc/sudoers.d/room
RUN for c in formscan; do \
      printf '#!/bin/bash\nexec sudo -n -u room /opt/room/lab.py %s "$@"\n' "$c" > /usr/local/bin/$c \
      && chmod 755 /usr/local/bin/$c; done

ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV PYTHONUNBUFFERED=1
