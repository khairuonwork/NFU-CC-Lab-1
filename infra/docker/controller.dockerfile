FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY service/controller/requirements.txt ./requirements.txt

RUN uv venv /app/.venv \
    && uv pip install \
        --python /app/.venv/bin/python \
        --requirement requirements.txt

COPY service/controller /app/controller

EXPOSE 8000

CMD ["uvicorn", "controller.app.main:app", "--host", "0.0.0.0", "--port", "8000"]