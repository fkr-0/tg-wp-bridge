FROM python:3.12-slim

# Create non-root user
RUN useradd -m appuser

WORKDIR /app

# Install dependencies (fastapi includes pydantic; we add pydantic-settings explicitly)
RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx pydantic-settings

# Copy package
COPY tg_wp_bridge /app/tg_wp_bridge

ENV PYTHONPATH=/app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "tg_wp_bridge.app:app", "--host", "0.0.0.0", "--port", "8000"]
