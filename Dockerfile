# Use Python 3.12 (stable) with pinned SHA digest for security
FROM python:3.12-slim@sha256:af4e85f1cac90dd3771e47292ea7c8a9830abfabbe4faa5c53f158854c2e819e

# Copy uv binary for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Apply security patches and create non-root user
RUN apt-get update && \
    apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -m -u 1000 appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy project files
COPY --chown=appuser:appuser pyproject.toml ./
COPY --chown=appuser:appuser paid_social_nav/ ./paid_social_nav/
COPY --chown=appuser:appuser mcp_server/ ./mcp_server/
COPY --chown=appuser:appuser configs/ ./configs/
COPY --chown=appuser:appuser sql/ ./sql/

# Switch to non-root user
USER appuser

# Install dependencies
RUN uv pip install --system -e .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
ENV PORT=8080
ENV ENVIRONMENT=production

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health').read()"

# Run server
CMD ["python", "-m", "mcp_server.server"]
