FROM python:3.11-slim

# Image for judging one sheet of alignment moves. It has no network when it runs.
#
#   /app/output   where the engineer's moves.csv is delivered
#   /tests        test.sh, the pytest test, the grader, and sealed/ with the definition of Unit 3
#   /app/data     the records the engineer had, for reference
#   /logs/verifier  the pytest report and the reward

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p /app/output

RUN pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5
RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 pandas==2.2.3

WORKDIR /tests
COPY . /tests/

# sealed/ is what a sheet is judged against, so nothing under /tests is left readable by any account but root.
# PYTHONDONTWRITEBYTECODE above keeps the interpreter from leaving a compiled copy of it anywhere.
RUN chown -R 0:0 /tests && chmod -R u=rwX,go= /tests && chmod u+x /tests/test.sh

RUN install -d -m 755 /app/data \
    && cp -R /tests/app_data/. /app/data/ \
    && chmod -R a=rX,u+w /app/data

RUN install -d -m 700 -o 0 -g 0 /logs/verifier
