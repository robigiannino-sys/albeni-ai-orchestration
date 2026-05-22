FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway injects PORT at runtime; default 8080 matches railway.internal convention
ENV PORT=8080
EXPOSE 8080

# No HEALTHCHECK here — Railway uses healthcheckPath="/health" from railway.toml
# which sends its own HTTP probes directly to the container PORT.
# A Dockerfile HEALTHCHECK (curl inside container) silently conflicts with
# Railway V2's probe mechanism and causes zero probes to reach uvicorn.

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
