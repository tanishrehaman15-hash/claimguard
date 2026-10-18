# Multi-arch image: builds on x86_64 and on IBM Z / LinuxONE (s390x).
FROM python:3.11-slim

# Build tools are needed on s390x where some wheels compile from source.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN test -f artifacts/metadata.json -a -f data/claims.csv || python -m claimguard.train

EXPOSE 8000 8501
CMD ["sh", "-c", "uvicorn claimguard.api:app --host 0.0.0.0 --port 8000 & streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true"]
