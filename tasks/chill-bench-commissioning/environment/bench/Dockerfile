FROM python:3.11-slim

RUN pip install --no-cache-dir numpy==2.1.3

WORKDIR /srv
COPY physics.py make_fleet.py bench_core.py server.py /srv/

ENV BENCH_PORT=8000
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["python", "server.py"]
