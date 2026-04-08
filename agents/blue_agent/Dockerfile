FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    auditd net-tools iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY base_agent.py .
COPY blue_agent/agent.py .
COPY blue_agent/main.py .

CMD ["python", "agent.py"]
