# Use Python 3.12 on Debian 12 (Bookworm), matching the Jenkins test environment.
FROM python:3.12-slim-bookworm

# Environment variables to optimize Python performance and container security
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install minimal system dependencies required by OpenCV and PyTorch, plus libcap2-bin for port 80 binding
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    gcc \
    python3-dev \
    libcap2-bin \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root system user and group for security compliance
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser

# Grant python3 binary capability to bind to privileged ports (<1024) as non-root
RUN setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set workspace permissions for non-root appuser
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn api.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}"]
