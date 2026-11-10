FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends sudo \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

# The agent runs as "agent" ([agent] user in task.toml). The inspection service and the superheater's sealed definition
# belong to "contractor"; the agent orders the inspection through the one sudo rule below (no arguments other than
# status or submit, the plan on standard input), reads the results it writes, and cannot read its code, the
# definition or its state. /app is root's with the sticky bit and group write for agent: the agent can create its
# own files there but cannot rename or replace /app/data or the contractor's /app/fieldwork.
RUN useradd --create-home --shell /bin/bash agent \
    && useradd --system --no-create-home --shell /usr/sbin/nologin contractor

WORKDIR /app
COPY data/ /app/data/
COPY fieldwork/ /opt/fieldwork/
COPY fieldwork-cmd /usr/local/bin/fieldwork

RUN chown -R root:root /app/data && chmod -R a+rX,go-w /app/data \
    && chown root:agent /app && chmod 1775 /app \
    && mkdir -p /app/output && chown agent:agent /app/output \
    && mkdir -p /app/fieldwork && chown contractor:contractor /app/fieldwork && chmod 755 /app/fieldwork \
    && chown -R contractor:contractor /opt/fieldwork \
    && chmod 700 /opt/fieldwork && chmod 600 /opt/fieldwork/*.py \
    && chmod 700 /opt/fieldwork/run \
    && mkdir -p /var/lib/fieldwork && chown contractor:contractor /var/lib/fieldwork && chmod 700 /var/lib/fieldwork \
    && chown root:root /usr/local/bin/fieldwork && chmod 755 /usr/local/bin/fieldwork \
    && printf '%s\n' 'Defaults!/opt/fieldwork/run !use_pty' \
        'agent ALL=(contractor) NOPASSWD: /opt/fieldwork/run status, /opt/fieldwork/run submit' > /etc/sudoers.d/fieldwork \
    && chmod 440 /etc/sudoers.d/fieldwork \
    && visudo -cf /etc/sudoers.d/fieldwork

ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV PYTHONUNBUFFERED=1
