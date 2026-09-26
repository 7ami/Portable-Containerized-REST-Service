# ==============================================================================
# Dockerfile: Portable Containerized REST Service
# ==============================================================================
# 1. Pinned base image: Debian-based Python 3.12 slim for reproducibility & minimal size
FROM python:3.12-slim

# 2. Recommended environment variables for Python in containers:
#    - PYTHONDONTWRITEBYTECODE: prevents python from writing .pyc files to disk
#    - PYTHONUNBUFFERED: forces stdout/stderr flush immediately so logs appear in real-time
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    REDIS_HOST=redis \
    REDIS_PORT=6379

# 3. Create an isolated application working directory
WORKDIR /app

# 4. Security Requirement: Create a dedicated non-root system user and group
#    Running as non-root prevents container breakout exploits
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser

# 5. Layer Caching: Copy dependencies first so Docker caches installed packages
#    Re-building code changes won't trigger re-installation of dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy application source code and grant ownership to the non-root user
COPY --chown=appuser:appgroup . .

# 7. Security: Switch to the non-root user for runtime execution
USER appuser

# 8. Document the port the container expects to listen on
EXPOSE 5000

# 9. Container Healthcheck: Queries the /health endpoint every 10s
#    Uses standard Python standard library (urllib) to avoid needing curl/wget installed
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", 5000)}/health')" || exit 1

# 10. Default container startup command
CMD ["python", "app.py"]
