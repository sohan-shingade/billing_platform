# Dockerfile
FROM python:3.11-slim

# Create a non-root user for safety
RUN useradd -m appuser
WORKDIR /app

# Copy only what we need
COPY backend/ backend/
COPY frontend/ frontend/

# Helpful Python envs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Default writable DB dir inside the image (can be overridden by a volume)
RUN mkdir -p backend/data && chown -R appuser:appuser /app
USER appuser

# The app reads PORT from env; PaaS usually injects it. Locally we'll map 8000.
EXPOSE 8000

# Start the stdlib server
CMD ["python", "backend/server.py"]
