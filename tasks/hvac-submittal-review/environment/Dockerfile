FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl poppler-utils sudo \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3 \
    openpyxl==3.1.5 \
    python-docx==1.1.2 \
    pypdf==5.1.0

# The agent runs as "agent" ([agent] user in task.toml). The field-verification service and the
# as-built definition belong to "facilities"; the agent can start the service through the one sudo
# rule below and cannot read its files or its state.
RUN useradd --create-home --shell /bin/bash agent \
    && useradd --system --no-create-home --shell /usr/sbin/nologin facilities

WORKDIR /app
COPY data/ /app/data/
COPY verify/ /opt/verify/
COPY start-verification /usr/local/bin/start-verification

RUN chown -R root:root /app/data && chmod -R a+rX,go-w /app/data \
    && chown agent:agent /app \
    && chown -R facilities:facilities /opt/verify \
    && chmod 700 /opt/verify && chmod 600 /opt/verify/*.py && chmod 700 /opt/verify/run-service \
    && mkdir -p /var/lib/verify && chown facilities:facilities /var/lib/verify && chmod 700 /var/lib/verify \
    && chown root:root /usr/local/bin/start-verification && chmod 755 /usr/local/bin/start-verification \
    && printf '%s\n' 'Defaults!/opt/verify/run-service !use_pty' \
        'agent ALL=(facilities) NOPASSWD: /opt/verify/run-service' > /etc/sudoers.d/verify \
    && chmod 440 /etc/sudoers.d/verify \
    && visudo -cf /etc/sudoers.d/verify

ENV VERIFY_URL=http://127.0.0.1:8000
ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV PYTHONUNBUFFERED=1
