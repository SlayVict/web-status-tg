FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock* ./

# Use uv as the package manager for speed and to match local env
RUN pip install --upgrade pip && pip install uv
RUN uv sync --no-dev --frozen

COPY . .

CMD ["uv", "run", "main.py"]
