FROM python:3.12-slim-bookworm

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bridge code
COPY app.py .

# Create non-root user
RUN addgroup --system --gid 1001 byd && \
    adduser --system --uid 1001 --ingroup byd byd && \
    chown -R byd:byd /app
USER byd

# Health check (MCP server responds to SSE requests)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; r=urllib.request.urlopen('http://localhost:8000/health'); assert r.status == 200" || exit 1

EXPOSE 8000

# Run MCP server with SSE transport
CMD ["python3", "app.py"]