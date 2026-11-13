FROM python:3.11-slim

# Verifier image for indicate.py. No network at run time.
#
#   /app/output      where the submitted indicate.py is put
#   /tests           this folder: the reward script, the pytest test, the checker, the six cell packages
#                    (cells/) and their sealed results (sealed/results/)
#   /logs/verifier   the reward, pytest's report and the checker's notes
#
# The checker runs as root and starts the submitted program as the user nobody, who can read neither /tests
# nor /logs/verifier. Each run gets a copy of one cell's package and a folder to write its table in.

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# One thread to a numerical library, so that a run's time is the time of one CPU.
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1

WORKDIR /tests
COPY . /tests/

# The versions are listed in requirements.txt: numpy==2.1.3 scipy==1.14.1 pandas==2.2.3 for the program,
# pytest==8.4.1 pytest-json-ctrf==0.3.5 for the test.
RUN pip install --no-cache-dir -r /tests/requirements.txt

# The submitted program arrives here.
RUN mkdir -p /app/output

# The program is started through setpriv, which the base image carries; the build fails here if it does not.
RUN setpriv --version

# Root alone reads the cells, their sealed results and the logs.
RUN chown -R 0:0 /tests && chmod -R u=rwX,go= /tests && chmod u+x /tests/test.sh
RUN mkdir -p /logs/verifier && chmod 700 /logs/verifier
