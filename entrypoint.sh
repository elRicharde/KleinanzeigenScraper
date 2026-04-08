#!/bin/bash
set -e

CRON_SCHEDULE="${CRON_SCHEDULE:-*/30 * * * *}"
RUN_ON_START="${RUN_ON_START:-false}"
LOG_FILE="/var/log/ek-scraper.log"

# Export current environment for cron (cron doesn't inherit env vars)
printenv | grep -v "no_proxy" > /etc/environment

# Write cron job
echo "${CRON_SCHEDULE} cd /app && ek-scraper run --data-store /app/data/datastore.json /app/config.json >> ${LOG_FILE} 2>&1" > /etc/cron.d/ek-scraper
echo "" >> /etc/cron.d/ek-scraper
chmod 0644 /etc/cron.d/ek-scraper
crontab /etc/cron.d/ek-scraper

echo "ek-scraper Docker container started"
echo "Cron schedule: ${CRON_SCHEDULE}"

# Optional: run once on start
if [ "${RUN_ON_START}" = "true" ]; then
    echo "Running initial scrape..."
    cd /app && ek-scraper run --data-store /app/data/datastore.json /app/config.json 2>&1 | tee -a "${LOG_FILE}"
    echo "Initial scrape complete."
fi

# Start cron and tail logs
cron
echo "Cron daemon started. Waiting for scheduled runs..."
exec tail -f "${LOG_FILE}"
