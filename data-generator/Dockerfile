FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY schemas.py .
COPY producer.py .
COPY ground_truth.py .
COPY control_server.py .
COPY entrypoint.py .

# Expose control server port
EXPOSE 8001

# Run the entrypoint
CMD ["python", "-u", "entrypoint.py"]
