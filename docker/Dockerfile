FROM python:3.12-slim

# Create non-root user
RUN useradd -m appuser

WORKDIR /app

RUN mkdir -p /app && pip install --no-cache-dir fastapi uvicorn[standard] httpx pydantic-settings click

# Copy package
COPY tg_wp_bridge /app/tg_wp_bridge
COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md

# Install the package to make CLI available
RUN cd /app && pip install -e .

# Ensure runtime-writeable directories exist for mappings and logs
RUN mkdir -p /app/data /app/logs \
    && chown -R appuser:appuser /app \
    && chmod -R u+rwX,g+rwX /app

ENV PYTHONPATH=/app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "tg_wp_bridge.app:app", "--host", "0.0.0.0", "--port", "8000"]
