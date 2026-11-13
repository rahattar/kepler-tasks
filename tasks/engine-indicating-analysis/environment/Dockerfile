FROM python:3.11-slim

# Where indicate.py is written.
#
#   /app/data/docs       IS-2, the indicating standard, and the format of a cell package
#   /app/data/examples   two sessions with their results to IS-2
#   /app/data/pending    two sessions that have not been calculated
#   /app/output          the program is left here, as indicate.py
#
# The data belong to root and are read-only to the account that writes the program, `agent`, which owns
# /app/output and nothing else under /app.

ENV PYTHONUNBUFFERED=1

# A run of the program is timed with one thread to a numerical library. The same setting here
# means a time measured while writing the program is the time that counts.
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1

# The interpreter's libraries, at the versions the program will be run with.
RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3

RUN useradd --create-home --user-group --shell /bin/bash agent

COPY data/ /app/data/
RUN chown -R root:root /app/data && chmod -R a=rX,u+w /app/data
RUN install -d -o agent -g agent -m 755 /app/output

WORKDIR /app
