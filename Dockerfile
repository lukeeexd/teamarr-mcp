FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY teamarr_mcp ./teamarr_mcp
RUN uv pip install --system --no-cache . \
    && useradd --create-home --uid 1000 mcp
USER mcp
ENV TEAMARR_URL=http://localhost:9195 \
    TEAMARR_MCP_TRANSPORT=http \
    TEAMARR_MCP_HOST=0.0.0.0 \
    TEAMARR_MCP_PORT=8000 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import socket; socket.create_connection(('127.0.0.1', 8000), 3)" || exit 1
ENTRYPOINT ["teamarr-mcp"]
