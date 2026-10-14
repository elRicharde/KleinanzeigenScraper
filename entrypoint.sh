#!/bin/bash
set -e

CRON_SCHEDULE="${CRON_SCHEDULE:-*/30 * * * *}"
RUN_ON_START="${RUN_ON_START:-false}"
CONFIG_DIR="/app/configs"
DATA_DIR="/app/data"
LOG_FILE="/var/log/ek-scraper.log"
EK_SCRAPER_BIN=$(which ek-scraper)
RUN_ALL_SCRIPT="/usr/local/bin/ek-scraper-run-all"

# Script that runs all configs one after another, so the rate limit of the scraper
# applies to all configs together instead of each config separately
cat > "${RUN_ALL_SCRIPT}" <<EOF
#!/bin/bash
cd /app
for config in "${CONFIG_DIR}"/*.json; do
    [ -f "\$config" ] || continue
    name=\$(basename "\$config" .json)
    echo "\$(date '+%Y-%m-%d %H:%M:%S') Scraping: \${name}"
    "${EK_SCRAPER_BIN}" run --data-store "${DATA_DIR}/datastore-\${name}.json" "\$config"
done
EOF
chmod +x "${RUN_ALL_SCRIPT}"

CONFIG_COUNT=0
for config in "${CONFIG_DIR}"/*.json; do
    [ -f "$config" ] || continue
    CONFIG_COUNT=$((CONFIG_COUNT + 1))
    name=$(basename "$config" .json)
    echo "  -> ${name} (datastore: datastore-${name}.json)"
done

# Build crontab with PATH so cron can find installed binaries.
# One job for all configs, flock skips a run while the previous one is still active.
{
    echo "PATH=$PATH"
    echo ""
    echo "${CRON_SCHEDULE} root flock -n /tmp/ek-scraper.lock ${RUN_ALL_SCRIPT} >> ${LOG_FILE} 2>&1"
    echo ""
} > /etc/cron.d/ek-scraper
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
    flock -n /tmp/ek-scraper.lock "${RUN_ALL_SCRIPT}" 2>&1 | tee -a "${LOG_FILE}"
    echo "Initial scrape complete."
fi

# Start cron and tail logs
cron
echo "Cron daemon started. Waiting for scheduled runs..."
exec tail -f "${LOG_FILE}"
