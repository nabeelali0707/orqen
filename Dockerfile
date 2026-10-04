FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir '.[web]' && useradd --create-home orqen && mkdir /data && chown orqen:orqen /data
USER orqen
EXPOSE 8080
CMD ["orqen", "serve", "--host", "0.0.0.0", "--database", "/data/service.sqlite3"]
