FROM python:3.11-slim

# System dependencies: cron + Playwright browser deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends cron && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files and install Python package
COPY pyproject.toml README.md LICENSE ./
COPY ek_scraper/ ./ek_scraper/
RUN pip install --no-cache-dir .

# Install Playwright Chromium + its system dependencies
RUN playwright install --with-deps chromium

# Create data directory and log file
RUN mkdir -p /app/data && touch /var/log/ek-scraper.log

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
