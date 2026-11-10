FROM python:3.11-slim

# numpy and scipy at the agent environment's pins, so a submitted controller imports the
# same libraries here that it was written against
RUN pip install --no-cache-dir \
    numpy==2.1.3 \
    scipy==1.14.1 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

# grade.py removes the sandbox user's System V IPC objects with ipcrm (util-linux, part of the
# base image); install it if a base-image change ever drops it, and fail the build if still missing
RUN command -v ipcrm >/dev/null \
    || (apt-get update && apt-get install -y --no-install-recommends util-linux \
        && rm -rf /var/lib/apt/lists/*) \
    && command -v ipcrm

# parent of the declared artifact, /app/controller.py, which harbor uploads here
RUN mkdir -p /app

COPY . /tests/

# The sealed simulator and benchmark are readable by root only; the submitted controller runs
# as the unprivileged user 'nobody' and cannot open them.
RUN chmod +x /tests/test.sh \
    && chmod 700 /tests \
    && mkdir -p /logs/verifier \
    && chmod 755 /logs/verifier

WORKDIR /tests
ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
