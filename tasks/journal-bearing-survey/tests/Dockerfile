FROM python:3.11-slim

# The verifier's image. A submitted bearing.py is run here on six sites it has not seen, with no network.
#
#   /app/output      bearing.py arrives here
#   /app/data        the documents and the three packages the program was written beside, where they were
#   /tests           test.sh, the pytest test, the checker (grade_program.py), the six packages (sites/),
#                    their results (sealed/truth/), and the laboratory's rule and books (lab/)
#   /logs/verifier   pytest's report, the findings for each site, the reward
#
# Who is who: the checker is root; the program runs as nobody; the laboratory is the checker. `labsample`
# here hands an order to the checker, which answers by /tests/lab/lab.py from books nobody cannot open.

WORKDIR /tests
RUN mkdir -p /app/output

RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3
RUN pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# A run is timed on one CPU with one thread to a numerical library, as it was where the program was written.
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1

COPY . /tests/

# setpriv starts the program as nobody; it comes with the base image, and the build stops here if it does not.
RUN command -v setpriv

# /app/data as the agent had it, and the verifier's labsample on the PATH.
RUN install -d -m 755 /app/data \
    && cp -r /tests/app_data/. /app/data/ \
    && chown -R 0:0 /app/data \
    && chmod -R a=rX,u+w /app/data \
    && install -m 755 /tests/lab/labsample /usr/local/bin/labsample

# What a submission is judged against is root's alone: the packages, the results, the books, the logs.
RUN chown -R 0:0 /tests \
    && chmod -R u=rwX,go= /tests \
    && chmod u+x /tests/test.sh \
    && install -d -m 700 -o 0 -g 0 /logs/verifier
