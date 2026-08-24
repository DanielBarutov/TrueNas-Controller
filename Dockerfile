FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev

COPY . .
RUN test -n "$(find repository/migrations/versions -maxdepth 1 -type f -name '*.py' ! -name '__init__.py' -print -quit)"
COPY docker/backend-entrypoint.sh /usr/local/bin/tnas-backend-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/tnas-backend-entrypoint \
    && chmod +x /usr/local/bin/tnas-backend-entrypoint

EXPOSE 8000

CMD ["bash", "/usr/local/bin/tnas-backend-entrypoint"]
