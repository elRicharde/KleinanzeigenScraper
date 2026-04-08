#!/bin/bash
set -e

CRON_SCHEDULE="${CRON_SCHEDULE:-*/30 * * * *}"
RUN_ON_START="${RUN_ON_START:-false}"
CONFIG_DIR="/app/configs"
DATA_DIR="/app/data"
LOG_FILE="/var/log/ek-scraper.log"
EK_SCRAPER_BIN=$(which ek-scraper)

# Build crontab with PATH so cron can find installed binaries
CONFIG_COUNT=0
{
    echo "PATH=$PATH"
    echo ""
} > /etc/cron.d/ek-scraper

for config in "${CONFIG_DIR}"/*.json; do
    [ -f "$config" ] || continue
    CONFIG_COUNT=$((CONFIG_COUNT + 1))
    name=$(basename "$config" .json)
    echo "${CRON_SCHEDULE} root cd /app && ${EK_SCRAPER_BIN} run --data-store ${DATA_DIR}/datastore-${name}.json ${config} >> ${LOG_FILE} 2>&1" >> /etc/cron.d/ek-scraper
    echo "  -> ${name} (datastore: datastore-${name}.json)"
done

echo "" >> /etc/cron.d/ek-scraper
chmod 0644 /etc/cron.d/ek-scraper

echo "ek-scraper Docker container started"
echo "Binary: ${EK_SCRAPER_BIN}"
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
        cd /app && "${EK_SCRAPER_BIN}" run --data-store "${DATA_DIR}/datastore-${name}.json" "$config" 2>&1 | tee -a "${LOG_FILE}"
    done
    echo "Initial scrape complete."
fi

# Start cron and tail logs
cron
echo "Cron daemon started. Waiting for scheduled runs..."
exec tail -f "${LOG_FILE}"
