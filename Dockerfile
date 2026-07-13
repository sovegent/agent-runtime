# Agent Runtime — Production Dockerfile
#
# Build:
#   docker build -t agent-runtime .
#
# Run (single agent via CLI):
#   docker run --env-file .env agent-runtime \
#     python main.py "Check disk usage and summarize"
#
# Run dashboard:
#   docker run --env-file .env -p 5001:5001 agent-runtime \
#     python -m dashboard.app
#
# Run event server:
#   docker run --env-file .env -p 8080:8080 agent-runtime \
#     python run_server.py
#
# Run scheduler:
#   docker run --env-file .env agent-runtime \
#     python run_scheduler.py

FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create runtime directories
RUN mkdir -p data/memory data/sessions workspace/code_sandbox

# Non-root user for security
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

# Default: show help (override with docker run command)
CMD ["python", "main.py", "--help"]
