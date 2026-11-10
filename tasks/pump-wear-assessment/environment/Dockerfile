FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

# The solver runs as "agent" ([agent] user in task.toml). The plant records are read-only; output goes to /app/output.
RUN useradd --create-home --shell /bin/bash agent

WORKDIR /app
COPY data/ /app/data/

RUN chown -R root:root /app/data && chmod -R a+rX,go-w /app/data \
    && mkdir -p /app/output && chown agent:agent /app/output

ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV PYTHONUNBUFFERED=1
