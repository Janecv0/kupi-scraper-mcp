FROM python:3.14.4-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir .

ENV PORT=8000
EXPOSE 8000

CMD ["kupi-scraper-mcp", "streamable-http"]
