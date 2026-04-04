FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8333"]
