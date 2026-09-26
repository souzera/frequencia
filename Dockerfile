FROM denoland/deno:bin-2.5.6 AS deno
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MEDIA_TIMEOUT=180
COPY --from=deno /deno /usr/local/bin/deno
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt
RUN useradd --create-home appuser
COPY app.py media.py gunicorn.conf.py ./
COPY templates ./templates
COPY static ./static
USER appuser
EXPOSE 5000
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:create_app()"]

