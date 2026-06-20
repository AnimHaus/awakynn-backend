FROM python:3.12-slim

WORKDIR /app

# Install SSL libraries and curl (used as reliable HTTP transport for R2 uploads)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        openssl \
        curl && \
    rm -rf /var/lib/apt/lists/* && \
    update-ca-certificates

# Install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
