FROM python:3.13-slim

# Copy uv binary for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY paid_social_nav/ ./paid_social_nav/
COPY mcp_server/ ./mcp_server/
COPY configs/ ./configs/
COPY sql/ ./sql/

# Install dependencies
RUN uv pip install --system -e .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run server
CMD ["python", "-m", "mcp_server.server"]
