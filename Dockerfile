FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY agent/requirements.txt /app/agent/requirements.txt
RUN pip install --no-cache-dir -r /app/agent/requirements.txt

# Copy BEA direct requirements data, SQL queries, scripts, tests, and agent application
COPY data/ /app/data/
COPY sql/ /app/sql/
COPY scripts/ /app/scripts/
COPY tests/ /app/tests/
COPY agent/ /app/agent/

# Environment defaults from Qwiklabs Cloud Run config
ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:/app/agent" \
    GOOGLE_CLOUD_PROJECT="qwiklabs-gcp-03-46ba9aeed89b" \
    GOOGLE_CLOUD_LOCATION="us-east1" \
    GOOGLE_GENAI_USE_VERTEXAI="TRUE" \
    BQ_DATASET="a4i_econ" \
    BQ_LOCATION="US" \
    BQ_GRAPH="LocalEconomy"

# Build-time E2E sanity gate across Member 1 + Member 2 + Member 3 contracts
RUN python3 -m unittest tests/test_member2_e2e.py

EXPOSE 8080

WORKDIR /app/agent

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
