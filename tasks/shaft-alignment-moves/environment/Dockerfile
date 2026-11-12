FROM python:3.11-slim

# Unit 3 at the end of its turnaround, as the rotating equipment engineer finds it.
#
#   /app/data            the records (read only)
#   /app/output          where the sheet of moves is to be written
#   /app/laser_reports   where the laser contractor leaves its reports
#   laservisit           the command that places the contractor's programme
#
# Two accounts. "agent" is the engineer. "contractor" is the laser contractor, and has no shell: it exists so
# that the definition of the unit the contractor measures, and the contractor's record of the one order it
# takes, belong to an account the engineer is not.

WORKDIR /app
ENV PYTHONUNBUFFERED=1

RUN groupadd agent && useradd -m -g agent -s /bin/bash agent \
    && groupadd contractor && useradd -M -g contractor -s /usr/sbin/nologin contractor

RUN apt-get update \
    && apt-get install -y --no-install-recommends sudo \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3

COPY data/ /app/data/
COPY rig/lab.py /opt/contractor/lab.py
COPY rig/sealed/ /opt/contractor/sealed/

# Records: root's, readable by all. Output: the engineer's. Reports: written by the contractor, read by the
# engineer.
RUN chown -R 0:0 /app /opt/contractor \
    && chmod 755 /app /opt/contractor /opt/contractor/lab.py \
    && chmod -R a=rX,u+w /app/data \
    && install -d -o agent -g agent -m 755 /app/output \
    && install -d -o contractor -g contractor -m 755 /app/laser_reports

# The contractor's own two directories. lab.py checks they are exactly this before it does anything.
RUN install -d -o contractor -g contractor -m 700 /opt/contractor/state \
    && chown -R contractor:contractor /opt/contractor/sealed \
    && chmod 700 /opt/contractor/sealed /opt/contractor/state \
    && chmod 600 /opt/contractor/sealed/*

# The engineer may run lab.py as the contractor and nothing else, and none of the engineer's environment goes
# with the call. laservisit is that call.
RUN echo 'Defaults!/opt/contractor/lab.py env_reset,!env_keep' > /etc/sudoers.d/contractor \
    && echo 'agent ALL=(contractor) NOPASSWD: /opt/contractor/lab.py' >> /etc/sudoers.d/contractor \
    && chmod 440 /etc/sudoers.d/contractor \
    && visudo -cf /etc/sudoers.d/contractor \
    && printf '%s\n' '#!/bin/bash' 'exec sudo -n -u contractor /opt/contractor/lab.py laservisit "$@"' > /usr/local/bin/laservisit \
    && chmod 755 /usr/local/bin/laservisit
