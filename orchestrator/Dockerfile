FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl openssh-client sshpass \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/orchestrator/requirements.txt
RUN pip install --no-cache-dir -r /app/orchestrator/requirements.txt

COPY . /app/orchestrator/

EXPOSE 8000
CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]
