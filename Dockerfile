FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY . .
RUN useradd --system --create-home sidewatch \
    && mkdir -p /app/data /app/artifacts \
    && chown sidewatch:sidewatch /app/data /app/artifacts

USER sidewatch

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
