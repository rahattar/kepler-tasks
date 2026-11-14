# The workshop in which ropes.py is written.
#
# /app/data is the company's material and stays as delivered: the standard RS-4 and the package format under
# docs/, two works with their results under examples/, one works without results under pending/. It is root's
# and read-only for `agent`, the account the work is done under. /app/output is agent's own; ropes.py is left
# there.
FROM python:3.11-slim

RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3

# ropes.py will be timed with a numerical library held to one thread. With the same three settings here, a time
# taken while the program is being written is a time of the same kind.
ENV OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --shell /bin/bash agent \
 && install -d -o agent -g agent -m 0755 /app/output

COPY --chown=root:root data /app/data
RUN chmod -R a-w,a+rX /app/data

WORKDIR /app
