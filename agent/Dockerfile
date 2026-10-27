FROM python:3.12-slim

WORKDIR /app

COPY agent/requirements.txt /app/agent/requirements.txt
RUN pip install --no-cache-dir -r /app/agent/requirements.txt

COPY data/ /app/data/
COPY sql/ /app/sql/
COPY agent/ /app/agent/

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python3", "-m", "agent.server"]
