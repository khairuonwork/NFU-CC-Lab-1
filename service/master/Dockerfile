FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.17 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# Install exactly the locked production dependencies first.
# Docker can reuse this layer while only application code changes.
COPY service/master/pyproject.toml service/master/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy only the Master application source after dependencies are cached.
COPY service/master/app ./app

# The Controller container does not need root privileges at runtime.
RUN groupadd --system cc \
    && useradd --system --gid cc --create-home cc \
    && chown -R cc:cc /app

USER cc

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health/live', timeout=2).read()" || exit 1

CMD [ "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]