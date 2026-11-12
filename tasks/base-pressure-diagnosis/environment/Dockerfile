FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends sudo \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

# The agent runs as "agent" ([agent] user in task.toml). The audit test order and the fleet's sealed definition
# belong to "contractor": the agent places the order through the one sudo rule below, reads the reports it writes,
# and cannot read its code, the definition or its state. /app is root's with the sticky bit and group write for
# agent, so the agent can create its own files there but cannot rename or replace /app/data or /app/vacwork.
RUN useradd --create-home --shell /bin/bash agent \
    && useradd --system --no-create-home --shell /usr/sbin/nologin contractor

WORKDIR /app
COPY data/ /app/data/
COPY rig/ /opt/vacwork/
COPY vacwork-cmd /usr/local/bin/vacwork

RUN chown -R root:root /app/data && chmod -R a+rX,go-w /app/data \
    && chown root:agent /app && chmod 1775 /app \
    && mkdir -p /app/output && chown agent:agent /app/output \
    && mkdir -p /app/vacwork && chown contractor:contractor /app/vacwork && chmod 755 /app/vacwork \
    && chown -R contractor:contractor /opt/vacwork \
    && chmod 700 /opt/vacwork && chmod 600 /opt/vacwork/vacwork.py \
    && chmod 700 /opt/vacwork/run \
    && chmod 700 /opt/vacwork/sealed && chmod 600 /opt/vacwork/sealed/* \
    && mkdir -p /var/lib/vacwork && chown contractor:contractor /var/lib/vacwork && chmod 700 /var/lib/vacwork \
    && chown root:root /usr/local/bin/vacwork && chmod 755 /usr/local/bin/vacwork \
    && printf '%s\n' 'Defaults!/opt/vacwork/run !use_pty' \
        'agent ALL=(contractor) NOPASSWD: /opt/vacwork/run status, /opt/vacwork/run submit' \
        > /etc/sudoers.d/vacwork \
    && chmod 440 /etc/sudoers.d/vacwork \
    && visudo -cf /etc/sudoers.d/vacwork

ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV PYTHONUNBUFFERED=1
