FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.17 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# ONNX Runtime requires the GNU OpenMP runtime on Debian slim.
RUN apt-get update \
    && apt-get install --no-install-recommends --yes libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install locked production dependencies before source code.
COPY service/worker/pyproject.toml service/worker/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the generic Worker source.
COPY service/worker/app ./app

# Worker cache and model cache are disposable local data.
RUN groupadd --system cc \
    && useradd --system --gid cc --create-home cc \
    && mkdir -p /var/lib/cc-worker/cache /var/lib/cc-worker/models \
    && chown -R cc:cc /app /var/lib/cc-worker

USER cc

CMD ["python", "-m", "app.main"]
