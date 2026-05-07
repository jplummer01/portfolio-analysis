FROM python:3.14-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY foundry/ foundry/

ARG AGENT_ROLE=analysis
ENV AGENT_ROLE=${AGENT_ROLE}
ENV PYTHONPATH=/app
EXPOSE 8080

# Agent to run is specified via AGENT_ROLE env var
CMD ["python", "-m", "foundry.entrypoint"]
