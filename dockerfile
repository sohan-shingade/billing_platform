FROM python:3.11-slim

# Create non-root user
RUN useradd -m appuser
WORKDIR /app

# Copy app
COPY backend/ backend/
COPY frontend/ frontend/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create writable dirs for the app user (both app paths and /data mount point)
RUN mkdir -p backend/data /data && chown -R appuser:appuser /app /data

USER appuser
EXPOSE 8000
CMD ["python", "backend/server.py"]
