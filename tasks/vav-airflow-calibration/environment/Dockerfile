FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl sudo \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

# The agent runs as "agent" ([agent] user in task.toml). The capture-hood visit service and the floor's sealed
# definition belong to "tab"; the agent starts the service through the one sudo rule below, reads the visit
# reports it writes, and cannot read its code, the definition or its state.
RUN useradd --create-home --shell /bin/bash agent \
    && useradd --system --no-create-home --shell /usr/sbin/nologin tab

WORKDIR /app
COPY data/ /app/data/
COPY hood/ /opt/hood/
COPY start-hood /usr/local/bin/start-hood

RUN chown -R root:root /app/data && chmod -R a+rX,go-w /app/data \
    && chown agent:agent /app && mkdir -p /app/output && chown agent:agent /app/output \
    && mkdir -p /app/visits && chown tab:tab /app/visits && chmod 755 /app/visits \
    && chown -R tab:tab /opt/hood \
    && chmod 700 /opt/hood && chmod 600 /opt/hood/*.py && chmod 700 /opt/hood/run-service \
    && mkdir -p /var/lib/hood && chown tab:tab /var/lib/hood && chmod 700 /var/lib/hood \
    && chown root:root /usr/local/bin/start-hood && chmod 755 /usr/local/bin/start-hood \
    && printf '%s\n' 'Defaults!/opt/hood/run-service !use_pty' \
        'agent ALL=(tab) NOPASSWD: /opt/hood/run-service ""' > /etc/sudoers.d/hood \
    && chmod 440 /etc/sudoers.d/hood \
    && visudo -cf /etc/sudoers.d/hood

ENV HOOD_URL=http://127.0.0.1:8000
ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV PYTHONUNBUFFERED=1
