FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    pandas==2.2.3

# The agent runs as "agent" ([agent] user in task.toml). /app/data and /app/tool are root's and read-only; the agent
# writes only to /app/output. /app itself is root's, so neither can be renamed or replaced.
RUN useradd --create-home --shell /bin/bash agent

WORKDIR /app
COPY data/ /app/data/
COPY tool/ /app/tool/

RUN chown -R root:root /app/data /app/tool && chmod -R a+rX,go-w /app/data /app/tool \
    && chown root:root /app && chmod 755 /app \
    && mkdir -p /app/output && chown agent:agent /app/output

ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV PYTHONUNBUFFERED=1
