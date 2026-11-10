FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl sudo \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

# The agent runs as "agent" ([agent] user in task.toml). The clean-and-test service and the bank's sealed definition
# belong to "contractor"; the agent starts the service through the one sudo rule below, reads the test reports it
# writes, and cannot read its code, the definition or its state.
# /app is root's with the sticky bit and group write for agent: the agent can create its own files there but
# cannot rename or replace /app/data or the service's /app/test_reports.
RUN useradd --create-home --shell /bin/bash agent \
    && useradd --system --no-create-home --shell /usr/sbin/nologin contractor

WORKDIR /app
COPY data/ /app/data/
COPY hxtest/ /opt/hxtest/
COPY start-hxtest /usr/local/bin/start-hxtest

RUN chown -R root:root /app/data && chmod -R a+rX,go-w /app/data \
    && chown root:agent /app && chmod 1775 /app \
    && mkdir -p /app/output && chown agent:agent /app/output \
    && mkdir -p /app/test_reports && chown contractor:contractor /app/test_reports && chmod 755 /app/test_reports \
    && chown -R contractor:contractor /opt/hxtest \
    && chmod 700 /opt/hxtest && chmod 600 /opt/hxtest/*.py && chmod 700 /opt/hxtest/run-service \
    && mkdir -p /var/lib/hxtest && chown contractor:contractor /var/lib/hxtest && chmod 700 /var/lib/hxtest \
    && chown root:root /usr/local/bin/start-hxtest && chmod 755 /usr/local/bin/start-hxtest \
    && printf '%s\n' 'Defaults!/opt/hxtest/run-service !use_pty' \
        'agent ALL=(contractor) NOPASSWD: /opt/hxtest/run-service ""' > /etc/sudoers.d/hxtest \
    && chmod 440 /etc/sudoers.d/hxtest \
    && visudo -cf /etc/sudoers.d/hxtest

ENV HXTEST_URL=http://127.0.0.1:8000
ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV PYTHONUNBUFFERED=1
