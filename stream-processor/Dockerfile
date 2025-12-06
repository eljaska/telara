FROM flink:1.18.1-java11

# Install Python and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for python
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Install PyFlink
RUN pip3 install apache-flink==1.18.1

# Download Kafka connector JAR
RUN mkdir -p /opt/flink/lib && \
    cd /opt/flink/lib && \
    curl -O https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.0.2-1.18/flink-sql-connector-kafka-3.0.2-1.18.jar

# Copy job files
RUN mkdir -p /opt/flink/jobs
COPY flink_job.py /opt/flink/jobs/

# Set working directory
WORKDIR /opt/flink

