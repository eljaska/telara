FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

# Create data directory
RUN mkdir -p /app/data

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY database.py .
COPY wellness.py .
COPY claude_agent.py .
COPY kafka_consumer.py .
COPY correlations.py .
COPY recommendations.py .
COPY digest.py .
COPY predictions.py .
COPY historical.py .
COPY main.py .

# Expose port
EXPOSE 8000

# Run the API server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
