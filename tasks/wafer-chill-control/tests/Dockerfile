FROM python:3.11-slim

# numpy and scipy at the agent environment's pins, so a submitted controller imports the
# same libraries here that it was written against
RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

# parent of the declared artifact, /app/controller.py, which harbor uploads here
RUN mkdir -p /app

COPY . /tests/

# The sealed plant and truth are readable by root only; the submitted controller runs as
# the unprivileged user 'nobody' and cannot open them.
RUN chmod +x /tests/test.sh \
    && chmod 700 /tests \
    && mkdir -p /logs/verifier \
    && chmod 755 /logs/verifier

WORKDIR /tests
ENV PYTHONUNBUFFERED=1
