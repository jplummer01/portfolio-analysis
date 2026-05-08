FROM public.ecr.aws/docker/library/python:3.14-slim

WORKDIR /app

# Build from the repository root, for example:
# docker build -f agents/recommendation/Dockerfile .
COPY agents/requirements.txt agents/requirements.txt
RUN pip install --no-cache-dir -r agents/requirements.txt

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/src/ src/
COPY agents/recommendation/main.py main.py

ENV PYTHONPATH=/app
EXPOSE 8088

CMD ["python", "main.py"]
