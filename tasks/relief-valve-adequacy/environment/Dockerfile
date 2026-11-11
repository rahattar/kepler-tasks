FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pandas==2.2.3

# The agent works as a user of its own. /app and the records under it belong to root, so they can be read but
# neither renamed nor replaced, and /app/output is the only place the agent may write.
RUN useradd --create-home --shell /bin/bash agent

COPY data/ /app/data/

RUN set -eu; \
    chown -R root:root /app /app/data; \
    chmod 755 /app; \
    chmod -R a+rX,go-w /app/data; \
    install -d -o agent -g agent -m 755 /app/output

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
