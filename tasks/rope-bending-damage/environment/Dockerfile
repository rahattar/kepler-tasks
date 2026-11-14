# The agent's workshop for writing ropes.py.
#   /app/data     what the steel company hands over, owned by root and read-only to the agent: RS-4 and the
#                 package format in docs/, forge_bay and plate_shop with their results in examples/, melt_hall
#                 without results in pending/
#   /app/output   the agent's own folder; ropes.py is delivered here
FROM python:3.11-slim

RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3

# Timings taken here are of the same kind as the verifier's, which holds every numerical library to one thread.
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1

RUN useradd --create-home --shell /bin/bash agent && install -d -o agent -g agent -m 0755 /app/output
COPY --chown=root:root data /app/data
RUN chmod -R a-w,a+rX /app/data
WORKDIR /app
