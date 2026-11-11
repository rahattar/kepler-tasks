FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

RUN apt-get update && apt-get install -y --no-install-recommends sudo && rm -rf /var/lib/apt/lists/*

# Two users. The agent ([agent] in task.toml) works in /app and writes only to /app/output. The test crew runs
# as "crew": it alone can read the sealed definition of the unit and its own booking records, and it writes its
# reports to /app/field_reports, which the agent may read. /opt/crew belongs to root, so neither user can
# rename or replace it.
RUN useradd --create-home --shell /bin/bash agent \
    && useradd --create-home --shell /usr/sbin/nologin crew

COPY data/ /app/data/

RUN set -eu; \
    chown -R root:root /app /app/data; \
    chmod 755 /app; \
    chmod -R a+rX,go-w /app/data; \
    install -d -o agent -g agent -m 755 /app/output; \
    install -d -o crew -g crew -m 755 /app/field_reports

COPY rig/lab.py /opt/crew/lab.py
COPY rig/sealed/ /opt/crew/sealed/

RUN set -eu; \
    mkdir -p /opt/crew/state; \
    chown root:root /opt/crew /opt/crew/lab.py; \
    chmod 755 /opt/crew /opt/crew/lab.py; \
    chown -R crew:crew /opt/crew/sealed /opt/crew/state; \
    chmod 700 /opt/crew/sealed /opt/crew/state; \
    chmod 600 /opt/crew/sealed/*

# The one privileged command: the agent may run the crew's program as crew, with no environment carried across.
RUN printf 'Defaults!/opt/crew/lab.py env_reset,!env_keep\nagent ALL=(crew) NOPASSWD: /opt/crew/lab.py\n' \
      > /etc/sudoers.d/crew \
    && chmod 440 /etc/sudoers.d/crew && visudo -cf /etc/sudoers.d/crew

RUN printf '#!/bin/bash\nexec sudo -n -u crew /opt/crew/lab.py fieldtest "$@"\n' > /usr/local/bin/fieldtest \
    && chmod 755 /usr/local/bin/fieldtest

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
