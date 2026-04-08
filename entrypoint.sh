#!/bin/bash
set -e

CRON_SCHEDULE="${CRON_SCHEDULE:-*/30 * * * *}"
RUN_ON_START="${RUN_ON_START:-false}"
CONFIG_DIR="/app/configs"
DATA_DIR="/app/data"
LOG_FILE="/var/log/ek-scraper.log"

# Export current environment for cron (cron doesn't inherit env vars)
printenv | grep -v "no_proxy" > /etc/environment

# Find all config JSON files and create a cron job for each
CONFIG_COUNT=0
> /etc/cron.d/ek-scraper

for config in "${CONFIG_DIR}"/*.json; do
    [ -f "$config" ] || continue
    CONFIG_COUNT=$((CONFIG_COUNT + 1))
    name=$(basename "$config" .json)
    echo "${CRON_SCHEDULE} cd /app && ek-scraper run --data-store ${DATA_DIR}/datastore-${name}.json ${config} >> ${LOG_FILE} 2>&1" >> /etc/cron.d/ek-scraper
    echo "  -> ${name} (datastore: datastore-${name}.json)"
done

echo "" >> /etc/cron.d/ek-scraper
chmod 0644 /etc/cron.d/ek-scraper
crontab /etc/cron.d/ek-scraper

echo "ek-scraper Docker container started"
echo "Cron schedule: ${CRON_SCHEDULE}"
echo "Configs found: ${CONFIG_COUNT}"

if [ "$CONFIG_COUNT" -eq 0 ]; then
    echo "WARNING: No config files found in ${CONFIG_DIR}/"
    echo "Mount your config files to ${CONFIG_DIR}/"
fi

# Optional: run once on start
if [ "${RUN_ON_START}" = "true" ]; then
    echo "Running initial scrape..."
    for config in "${CONFIG_DIR}"/*.json; do
        [ -f "$config" ] || continue
        name=$(basename "$config" .json)
        echo "  Scraping: ${name}"
        cd /app && ek-scraper run --data-store "${DATA_DIR}/datastore-${name}.json" "$config" 2>&1 | tee -a "${LOG_FILE}"
    done
    echo "Initial scrape complete."
fi

# Start cron and tail logs
cron
echo "Cron daemon started. Waiting for scheduled runs..."
exec tail -f "${LOG_FILE}"
