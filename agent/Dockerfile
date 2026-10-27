FROM python:3.12-slim

WORKDIR /app/agent

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/agent/requirements.txt
RUN pip install --no-cache-dir -r /app/agent/requirements.txt

COPY . /app/agent/

ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    GOOGLE_CLOUD_PROJECT="qwiklabs-gcp-03-46ba9aeed89b" \
    GOOGLE_CLOUD_LOCATION="us-east1" \
    GOOGLE_GENAI_USE_VERTEXAI="TRUE" \
    BQ_DATASET="a4i_econ" \
    BQ_LOCATION="US" \
    BQ_GRAPH="LocalEconomy"

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
