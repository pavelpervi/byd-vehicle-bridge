FROM python:3.12-slim-bookworm

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy package source
COPY src/ ./src/

# Document runtime defaults (overridable via env_file or -e)
ENV BYD_PORT=8000
ENV PYTHONPATH=/app/src

# Create non-root user
RUN addgroup --system --gid 1001 byd && \
    adduser --system --uid 1001 --ingroup byd byd && \
    chown -R byd:byd /app
USER byd

# Health check: verify the MCP server process is alive and responding
# Uses a simple TCP connection check since MCP uses SSE, not REST
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import socket; s=socket.create_connection(('localhost', ${BYD_PORT:-8000}), timeout=5); s.close()" || exit 1

EXPOSE 8000

# Run MCP server with SSE transport
CMD ["python3", "-m", "byd_bridge"]