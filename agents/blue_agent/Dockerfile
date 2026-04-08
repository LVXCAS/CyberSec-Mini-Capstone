FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    auditd net-tools iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY main.py .

CMD ["python", "main.py"]
