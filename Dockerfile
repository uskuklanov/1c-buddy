# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install the package itself. The stdio extra is not needed inside the container.
COPY pyproject.toml README.md LICENSE ./
COPY ./app ./app
RUN pip install --no-cache-dir ".[http]"

# App listens on 6002
EXPOSE 6002

# Healthcheck without extra packages.
# ProxyHandler({}) keeps the loopback probe off any HTTP_PROXY inherited from env_file.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request,sys; o=urllib.request.build_opener(urllib.request.ProxyHandler({})); sys.exit(0 if o.open('http://127.0.0.1:6002/health').getcode()==200 else 1)"

# Run FastAPI (OpenAI /v1, MCP /mcp, Web chat /chat)
CMD ["1c-buddy", "http", "--host", "0.0.0.0", "--port", "6002"]
