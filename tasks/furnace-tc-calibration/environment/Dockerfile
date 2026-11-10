FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl sudo \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

# The agent runs as "agent" ([agent] user in task.toml). The TC-wafer run service and the bay's sealed definition
# belong to "metrology"; the agent starts the service through the one sudo rule below, reads the run reports it
# writes, and cannot read its code, the definition or its state.
# /app is root's with the sticky bit and group write for agent: the agent can create its own files there but
# cannot rename or replace /app/data or the service's /app/runs.
RUN useradd --create-home --shell /bin/bash agent \
    && useradd --system --no-create-home --shell /usr/sbin/nologin metrology

WORKDIR /app
COPY data/ /app/data/
COPY tcwafer/ /opt/tcwafer/
COPY start-tcwafer /usr/local/bin/start-tcwafer

RUN chown -R root:root /app/data && chmod -R a+rX,go-w /app/data \
    && chown root:agent /app && chmod 1775 /app \
    && mkdir -p /app/output && chown agent:agent /app/output \
    && mkdir -p /app/runs && chown metrology:metrology /app/runs && chmod 755 /app/runs \
    && chown -R metrology:metrology /opt/tcwafer \
    && chmod 700 /opt/tcwafer && chmod 600 /opt/tcwafer/*.py && chmod 700 /opt/tcwafer/run-service \
    && mkdir -p /var/lib/tcwafer && chown metrology:metrology /var/lib/tcwafer && chmod 700 /var/lib/tcwafer \
    && chown root:root /usr/local/bin/start-tcwafer && chmod 755 /usr/local/bin/start-tcwafer \
    && printf '%s\n' 'Defaults!/opt/tcwafer/run-service !use_pty' \
        'agent ALL=(metrology) NOPASSWD: /opt/tcwafer/run-service ""' > /etc/sudoers.d/tcwafer \
    && chmod 440 /etc/sudoers.d/tcwafer \
    && visudo -cf /etc/sudoers.d/tcwafer

ENV TCWAFER_URL=http://127.0.0.1:8000
ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV PYTHONUNBUFFERED=1
