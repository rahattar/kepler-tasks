FROM python:3.11-slim

# Where bearing.py is written.
#
#   /app/data/docs       LS-3 and the format of a site package
#   /app/data/examples   two site packages with their results to LS-3
#   /app/data/pending    one site package without results
#   /app/output          the program goes here
#   labsample            places a package's laboratory order; the laboratory here answers for those three sites
#
# The oil laboratory is an account of its own, `lab`, without a shell. Its books of analyses are readable by
# that account alone, so the program's author, the account `agent`, gets a figure only by ordering it.

ENV PYTHONUNBUFFERED=1
# A run of the program is timed on one CPU with the numerical libraries held to one thread; the same holds here.
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends sudo \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3

RUN useradd --create-home --user-group --shell /bin/bash agent \
    && useradd --system --user-group --no-create-home --shell /usr/sbin/nologin lab

WORKDIR /app
COPY data/ /app/data/
RUN chown -R root:root /app/data \
    && chmod -R a=rX,u+w /app/data \
    && install -d -o agent -g agent -m 755 /app/output

# The laboratory: its program, its books, the orders it has taken, and the wrapper that reaches it.
COPY rig/lab.py /opt/lab/lab.py
COPY rig/sealed/ /opt/lab/sealed/
COPY rig/labsample /usr/local/bin/labsample
COPY rig/sudoers /etc/sudoers.d/lab
RUN chown root:root /opt/lab /opt/lab/lab.py /usr/local/bin/labsample /etc/sudoers.d/lab \
    && chmod 755 /opt/lab /opt/lab/lab.py /usr/local/bin/labsample \
    && chown -R lab:lab /opt/lab/sealed \
    && chmod 700 /opt/lab/sealed \
    && chmod 600 /opt/lab/sealed/*.json \
    && install -d -o lab -g lab -m 700 /opt/lab/state \
    && chmod 440 /etc/sudoers.d/lab \
    && visudo -cf /etc/sudoers.d/lab
