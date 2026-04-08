# ek-scraper

Automatischer Scraper für [kleinanzeigen.de](https://www.kleinanzeigen.de) mit Benachrichtigungen bei neuen Anzeigen.

`ek-scraper` überwacht beliebig viele Kleinanzeigen-Suchen und benachrichtigt dich per **Telegram**, **Pushover** oder **ntfy.sh**, sobald neue Inserate erscheinen. Dank Headless-Browser (Playwright/Chromium) werden auch JavaScript-geschützte Seiten zuverlässig geladen.

## Features

- Headless-Browser-Scraping via Playwright (Chromium) — umgeht Bot-Detection und JavaScript-Schutz
- Mehrere Suchen parallel überwachen
- Automatische Pagination — alle Ergebnisseiten werden durchsucht
- Flexible Filter: Top-Ads ausblenden, Regex-Muster zum Ausschließen
- Benachrichtigungen via **Telegram**, **Pushover** und/oder **ntfy.sh**
- Persistenter Datenspeicher — nur wirklich neue Anzeigen lösen Benachrichtigungen aus
- Pruning — veraltete Anzeigen automatisch aus dem Datenspeicher entfernen
- Ideal für Cronjobs / regelmäßige Ausführung
- **Docker-Support** — ein Container, beliebig viele Configs, integrierter Cron

## Installation

### Option A: Docker (empfohlen)

Voraussetzung: [Docker](https://docs.docker.com/engine/install/) mit Docker Compose.

```sh
git clone https://github.com/elRicharde/KleinanzeigenScraper.git
cd KleinanzeigenScraper

# Configs-Ordner anlegen und Konfigurationen hinzufügen
mkdir -p configs
cp config-davinci-pc.example configs/config-pc.json
# configs/config-pc.json anpassen (Suchen, Telegram-Token etc.)

# Bauen & starten
docker compose up -d

# Logs ansehen
docker compose logs -f
```

Der Container erkennt automatisch alle `*.json`-Dateien im `configs/`-Ordner und erstellt für jede einen Cron-Job mit eigenem Datenspeicher.

**Neue Suche hinzufügen:** JSON-Datei in `configs/` legen → `docker compose restart`

**Suche entfernen:** JSON-Datei aus `configs/` löschen → `docker compose restart`

**Umgebungsvariablen** (in `docker-compose.yml`):

| Variable | Standard | Beschreibung |
|---|---|---|
| `CRON_SCHEDULE` | `*/15 * * * *` | Cron-Zeitplan für alle Configs |
| `RUN_ON_START` | `false` | Beim Container-Start sofort einmal scrapen |

### Option B: Manuelle Installation

### Voraussetzungen

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) (empfohlen) oder pip

### Installieren

```sh
uv tool install ek-scraper
```

Oder mit pip:

```sh
pip install ek-scraper
```

### Playwright-Browser einrichten

Nach der Installation muss einmalig der Chromium-Browser für Playwright heruntergeladen werden:

```sh
playwright install chromium
playwright install-deps chromium
```

> `install-deps` installiert die benötigten System-Bibliotheken (Linux). Unter macOS/Windows ist dieser Schritt in der Regel nicht nötig.

## Schnellstart

### 1. Konfiguration erstellen

```sh
ek-scraper create-config config.json
```

### 2. Konfiguration anpassen

Bearbeite `config.json` — füge deine Suchen und Benachrichtigungseinstellungen hinzu (siehe [Konfiguration](#konfiguration)).

### 3. Erster Lauf (Datenspeicher füllen, ohne Benachrichtigungen)

```sh
ek-scraper run --no-notifications --data-store datastore.json config.json
```

Beim ersten Lauf werden alle aktuellen Anzeigen erfasst und im Datenspeicher gespeichert. So bekommst du beim nächsten Lauf nur wirklich **neue** Anzeigen gemeldet.

### 4. Regulärer Lauf (mit Benachrichtigungen)

```sh
ek-scraper run --data-store datastore.json config.json
```

## CLI-Befehle

### `ek-scraper run`

Führt den Scraper aus und sendet Benachrichtigungen für neue Anzeigen.

```
ek-scraper run [OPTIONEN] CONFIG_FILE
```

| Option                | Beschreibung                                                         |
| --------------------- | -------------------------------------------------------------------- |
| `--data-store PFAD`   | Pfad zur JSON-Datei für den Datenspeicher (Standard: `~/ek-scraper-datastore.json`) |
| `--temp-data-store`   | Temporären Datenspeicher verwenden (nicht persistent)                |
| `--no-notifications`  | Keine Benachrichtigungen senden                                      |
| `--prune`             | Veraltete Anzeigen beim Schließen aus dem Datenspeicher entfernen    |
| `-v, --verbose`       | Debug-Ausgabe aktivieren                                             |

> `--data-store` und `--temp-data-store` schließen sich gegenseitig aus.

### `ek-scraper create-config`

Erstellt eine Beispiel-Konfigurationsdatei.

```
ek-scraper create-config CONFIG_FILE
```

### `ek-scraper prune`

Entfernt Anzeigen aus dem Datenspeicher, die in keiner Suche mehr auftauchen.

```
ek-scraper prune --data-store PFAD CONFIG_FILE
```

## Konfiguration

Die Konfiguration erfolgt über eine JSON-Datei mit drei Abschnitten:

```json
{
  "filter": { ... },
  "notifications": { ... },
  "searches": [ ... ]
}
```

### Suchen (`searches`)

Ein Array von Suchen, die überwacht werden sollen.

| Feld        | Typ     | Pflicht | Standard | Beschreibung                                      |
| ----------- | ------- | ------- | -------- | ------------------------------------------------- |
| `name`      | string  | ja      | —        | Beschreibender Name der Suche                     |
| `url`       | string  | ja      | —        | URL der ersten Ergebnisseite auf kleinanzeigen.de |
| `recursive` | boolean | nein    | `true`   | Alle Ergebnisseiten (Pagination) durchsuchen      |

**Beispiel:**

```json
"searches": [
  {
    "name": "Wohnungen in Hamburg Altona",
    "url": "https://www.kleinanzeigen.de/s-wohnung-mieten/altona/c203l9497",
    "recursive": true
  },
  {
    "name": "E-Bikes in Berlin",
    "url": "https://www.kleinanzeigen.de/s-fahrraeder/berlin/e-bike/k0c217l3331",
    "recursive": false
  }
]
```

### Filter (`filter`)

Client-seitige Filter zum Ausschließen und Einschließen bestimmter Anzeigen.

| Feld                   | Typ      | Standard | Beschreibung                                            |
| ---------------------- | -------- | -------- | ------------------------------------------------------- |
| `exclude_topads`       | boolean  | `true`   | Gesponserte Top-Anzeigen ausschließen                   |
| `exclude_patterns`     | string[] | `[]`     | Regex-Muster — Anzeigen mit passendem Titel oder Beschreibung werden ignoriert |
| `require_all_patterns` | string[] | `[]`     | Regex-Muster — **alle** müssen im Titel oder der Beschreibung matchen (AND-Verknüpfung). Innerhalb eines Musters kann Regex-OR (`|`) verwendet werden |

**Logik:**
- `exclude_patterns`: Anzeige wird ausgeschlossen wenn **irgendein** Muster matcht (OR)
- `require_all_patterns`: Anzeige wird ausgeschlossen wenn **nicht alle** Muster matchen (AND)

So lassen sich komplexe Abfragen bauen: `(Bedingung1_a ODER Bedingung1_b) UND (Bedingung2_a ODER Bedingung2_b)`

**Beispiel:**

```json
"filter": {
  "exclude_topads": true,
  "exclude_patterns": [
    "(?i)\\b(defekt|bastler|tausch)\\b"
  ],
  "require_all_patterns": [
    "(?i)(64\\s*gb|96\\s*gb|128\\s*gb)",
    "(?i)(nvme|m\\.?2|ssd)"
  ]
}
```

**Pattern-Referenz:**

Die Patterns verwenden Python-Regex-Syntax. `(?i)` aktiviert Groß-/Kleinschreibung-ignorieren, `\\s*` matcht optionale Leerzeichen, `|` ist ODER innerhalb einer Gruppe.

| Pattern | Matcht | Matcht nicht |
|---------|--------|-------------|
| `(?i)(48\\s*gb\|64\\s*gb\|96\\s*gb\|128\\s*gb)` | `64GB`, `64 GB`, `128gb`, `96 Gb` | `32GB`, `viel RAM`, `16gb` |
| `(?i)(nvme\|m\\.?2\|ssd\\s*(1\|2)\\s*tb)` | `NVMe`, `M.2`, `M2`, `SSD 1TB`, `2 TB SSD` | `HDD`, `Festplatte`, `256GB SSD` |
| `(?i)\\b(defekt\|bastler\|tausch)\\b` | `Defekt`, `BASTLER`, `Tausch` | `defekter` (da `\\b` Wortgrenzen prüft) |

> **Hinweis:** Alle Patterns werden sowohl auf den **Titel** als auch auf die **Beschreibung** der Anzeige angewendet. Es reicht wenn der Suchbegriff in einem der beiden Felder vorkommt.

### Benachrichtigungen (`notifications`)

Alle Backends sind optional und können kombiniert werden. Pro Suche wird eine Benachrichtigung gesendet, wenn neue Anzeigen gefunden werden.

#### Telegram

Benachrichtigungen über einen Telegram-Bot. Jede Nachricht enthält die einzelnen Anzeigen als klickbare Links mit Preis sowie einen Link zur Suchergebnisseite:

```
Dresden Workstation 64GB

🤖 Found 2 new ads

• iMac Pro 2017 5K 27" | 14-Core | 64GB | 2TB SSD Workstation PC – 1.399 €
• High-End Workstation PC - Ryzen 9 5950X|64GB Ram| X570|1TB NVMe – 1.150 € VB

Zur Suche
```

```json
"notifications": {
  "telegram": {
    "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    "chat_id": "-1001234567890",
    "link_preview": false
  }
}
```

| Feld           | Typ     | Pflicht | Standard | Beschreibung                      |
| -------------- | ------- | ------- | -------- | --------------------------------- |
| `bot_token`    | string  | ja      | —        | Bot-Token vom BotFather           |
| `chat_id`      | string  | ja      | —        | Chat-/Gruppen-/Kanal-ID          |
| `link_preview` | boolean | nein    | `false`  | Link-Vorschau in Nachrichten anzeigen |

**Telegram einrichten:**

1. Öffne [@BotFather](https://t.me/BotFather) in Telegram
2. Sende `/newbot` und folge den Anweisungen → du erhältst den `bot_token`
3. Starte eine Konversation mit deinem Bot oder füge ihn einer Gruppe hinzu
4. Rufe `https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates` auf → lies die `chat_id` aus dem `chat.id` Feld ab

#### Pushover

Push-Benachrichtigungen über [Pushover](https://pushover.net/).

```json
"notifications": {
  "pushover": {
    "token": "<app-api-token>",
    "user": "<user-api-token>",
    "device": []
  }
}
```

| Feld     | Typ      | Pflicht | Standard       | Beschreibung                                |
| -------- | -------- | ------- | -------------- | ------------------------------------------- |
| `token`  | string   | ja      | —              | API-Token der Pushover-App                  |
| `user`   | string   | ja      | —              | API-Token des Pushover-Nutzers              |
| `device` | string[] | nein    | `[]` (alle)    | Gerätenamen, die benachrichtigt werden      |

#### ntfy.sh

Push-Benachrichtigungen über [ntfy.sh](https://ntfy.sh/).

```json
"notifications": {
  "ntfy.sh": {
    "topic": "ek-scraper-dein-geheimer-name",
    "priority": 3
  }
}
```

| Feld       | Typ     | Pflicht | Standard | Beschreibung                                       |
| ---------- | ------- | ------- | -------- | -------------------------------------------------- |
| `topic`    | string  | ja      | —        | Topic-Name (sollte schwer zu erraten sein)          |
| `priority` | integer | nein    | `3`      | Priorität: 1 (niedrig) bis 5 (dringend)            |

> Topic-Namen sind öffentlich. Verwende einen schwer erratbaren Namen, z.B.:
> ```sh
> echo "ek-scraper-$(uuidgen)"
> ```

### Vollständiges Konfigurationsbeispiel

```json
{
  "filter": {
    "exclude_topads": true,
    "exclude_patterns": [".*[Mm]akler.*", ".*[Pp]rovision.*"]
  },
  "notifications": {
    "telegram": {
      "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
      "chat_id": "-1001234567890",
      "link_preview": false
    }
  },
  "searches": [
    {
      "name": "Wohnungen in Hamburg Altona",
      "url": "https://www.kleinanzeigen.de/s-wohnung-mieten/altona/c203l9497",
      "recursive": true
    }
  ]
}
```

## Regelmäßige Ausführung

### Docker (empfohlen)

Bei der Docker-Installation ist der Cron bereits im Container integriert. Das Intervall wird über die `CRON_SCHEDULE`-Umgebungsvariable in der `docker-compose.yml` gesteuert:

```yaml
environment:
  - CRON_SCHEDULE=*/15 * * * *
```

Nützliche Docker-Befehle:

```sh
# Status prüfen
docker compose ps

# Logs ansehen
docker compose logs -f

# Neustart (z.B. nach Config-Änderung)
docker compose restart

# Manuellen Scrape-Lauf auslösen
docker exec ek-scraper ek-scraper run --data-store /app/data/datastore-config-pc.json /app/configs/config-pc.json
```

### Cronjob (manuelle Installation)

Um `ek-scraper` ohne Docker automatisch regelmäßig auszuführen, richte einen Cronjob ein:

```sh
crontab -e
```

**Wichtig:** Verwende in Cronjobs immer den **vollen Pfad** zu `ek-scraper`, da Cron eine eingeschränkte `PATH`-Umgebung hat. Den Pfad findest du mit `which ek-scraper`.

Beispiel — alle 30 Minuten ausführen, mit vollem Pfad und Logging:

```
*/30 * * * * cd ~/ek-scraper && /home/user/.local/bin/ek-scraper run --data-store datastore.json config.json >> ~/ek-scraper.log 2>&1
```

Beispiel — mehrere Configs mit unterschiedlichen Intervallen:

```
*/15 * * * * cd ~/ek-scraper && /home/user/.local/bin/ek-scraper run --data-store datastore-pc.json config-pc.json >> ~/ek-scraper-pc.log 2>&1
*/30 * * * * cd ~/ek-scraper && /home/user/.local/bin/ek-scraper run --data-store datastore-moebel.json config-moebel.json >> ~/ek-scraper-moebel.log 2>&1
```

> **Hinweis:** `>> ~/ek-scraper.log 2>&1` leitet sowohl stdout als auch stderr in eine Logdatei um. Ohne dieses Redirect gehen Fehlermeldungen verloren und der Scraper scheitert still.

> Führe den Scraper nicht zu häufig aus, um eine IP-Sperre durch kleinanzeigen.de zu vermeiden. Ein Intervall von 15–30 Minuten ist empfehlenswert.

Ein nützliches Tool zur Erstellung von Cron-Ausdrücken: [crontab.guru](https://crontab.guru/)

## Server-Einrichtung (Schritt für Schritt)

### Docker-Setup

Komplette Anleitung für einen frischen Linux-Server mit Docker.

#### 1. Docker installieren

```sh
# Docker installieren (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Neu einloggen damit die Gruppenänderung greift
```

#### 2. Repository klonen

```sh
git clone https://github.com/elRicharde/KleinanzeigenScraper.git
cd KleinanzeigenScraper
```

#### 3. Konfigurationen anlegen

```sh
mkdir -p configs

# Beispiel-Config kopieren und anpassen
cp config-davinci-pc.example configs/config-pc.json
# configs/config-pc.json bearbeiten: Suchen, Telegram-Token, Chat-ID etc.
```

Pflichtfelder in der Config:
- Mindestens eine Suche mit `name` und `url`
- Benachrichtigungs-Credentials (z.B. Telegram `bot_token` + `chat_id`)

> **Tipp:** Mehrere Config-Dateien im `configs/`-Ordner anlegen — jede wird automatisch erkannt.

#### 4. Datenspeicher übernehmen (optional)

Wenn du von einem bestehenden Setup umziehst, kannst du die bisherigen Datenspeicher in das Docker-Volume kopieren:

```sh
# Container einmal starten damit das Volume erstellt wird
docker compose up -d && docker compose down

# Datenspeicher ins Volume kopieren
docker run --rm -v kleinanzeigenscraper_ek-scraper-data:/data -v $(pwd):/src alpine \
  cp /src/datastore-pc.json /data/datastore-config-pc.json
```

Ohne Datenspeicher werden beim ersten Lauf alle aktuellen Anzeigen als "neu" erfasst — du bekommst dann einmalig viele Benachrichtigungen.

#### 5. Starten

```sh
docker compose up -d
```

#### 6. Prüfen ob es läuft

```sh
# Container-Status
docker compose ps

# Logs ansehen
docker compose logs -f

# Datenspeicher prüfen (im Volume)
docker exec ek-scraper ls -la /app/data/
```

> **Zusammenfassung:** Docker installieren → Repo klonen → Configs in `configs/` anlegen → `docker compose up -d`. Fertig.

---

### Manuelle Einrichtung (ohne Docker)

Komplette Anleitung, um `ek-scraper` ohne Docker auf einem frischen Linux-Server einzurichten.

#### 1. Python und uv installieren

```sh
# Python 3.11+ prüfen
python3 --version

# uv installieren (falls noch nicht vorhanden)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 2. ek-scraper installieren

```sh
uv tool install ek-scraper
```

#### 3. Playwright-Browser einrichten

```sh
playwright install chromium
playwright install-deps chromium   # installiert System-Bibliotheken (nur Linux)
```

#### 4. Konfiguration erstellen

```sh
# Beispielconfig erzeugen und anpassen
ek-scraper create-config config.json
```

Oder eine vorhandene Config-Datei vom alten Server kopieren.

Pflichtfelder in der Config:
- Mindestens eine Suche mit `name` und `url`
- Benachrichtigungs-Credentials (z.B. Telegram `bot_token` + `chat_id`)

> **Tipp:** Mehrere Configs für verschiedene Suchkategorien anlegen (z.B. `config-pc.json`, `config-moebel.json`).

#### 5. Datenspeicher übernehmen (optional)

Wenn du von einem anderen Server umziehst, kopiere die Datenspeicher-Datei mit:

```sh
scp alter-server:~/ek-scraper-datastore.json ~/
```

Ohne Datenspeicher werden beim ersten Lauf alle aktuellen Anzeigen als "neu" erfasst — du bekommst dann einmalig viele Benachrichtigungen.

#### 6. Erster Testlauf

```sh
# Ohne Benachrichtigungen — füllt nur den Datenspeicher
ek-scraper run --no-notifications --data-store datastore.json config.json

# Mit Benachrichtigungen — prüfen ob alles funktioniert
ek-scraper run --data-store datastore.json config.json
```

#### 7. Cronjob einrichten

```sh
# Vollen Pfad ermitteln
which ek-scraper
# z.B. /home/techniker/.local/bin/ek-scraper

crontab -e
```

Beispiel — alle 30 Minuten, mit vollem Pfad und Logging:

```
*/30 * * * * cd ~/ek-scraper && /home/techniker/.local/bin/ek-scraper run --data-store datastore.json config.json >> ~/ek-scraper.log 2>&1
```

Beispiel — mehrere Configs mit unterschiedlichen Intervallen:

```
*/15 * * * * cd ~/ek-scraper && /home/techniker/.local/bin/ek-scraper run --data-store datastore-pc.json config-pc.json >> ~/ek-scraper-pc.log 2>&1
*/30 * * * * cd ~/ek-scraper && /home/techniker/.local/bin/ek-scraper run --data-store datastore-moebel.json config-moebel.json >> ~/ek-scraper-moebel.log 2>&1
```

#### 8. Prüfen ob es läuft

```sh
# Cron-Ausführungen im Syslog prüfen
sudo grep ek-scraper /var/log/syslog | tail -10

# Datenspeicher prüfen — wann zuletzt geändert?
ls -la ~/ek-scraper/datastore*.json

# Logdatei prüfen (falls Logging eingerichtet)
tail -50 ~/ek-scraper.log
```

> **Zusammenfassung:** `uv` + `playwright` installieren → Config anlegen → optional Datenspeicher mitnehmen → Cronjob mit vollem Pfad + Logging einrichten. Fertig.

## Troubleshooting

### Docker

**Container-Status prüfen:**

```sh
docker compose ps
docker compose logs -f
```

**Manueller Testlauf im Container:**

```sh
docker exec ek-scraper ek-scraper run --data-store /app/data/datastore-config-pc.json /app/configs/config-pc.json
```

**Container neu bauen** (nach Code-Updates):

```sh
git pull
docker compose up -d --build
```

**Datenspeicher einsehen:**

```sh
docker exec ek-scraper ls -la /app/data/
```

| Problem | Ursache | Lösung |
|---------|---------|--------|
| Container startet, aber keine Scrapes | Keine Config-Dateien gefunden | Prüfen ob `configs/`-Ordner existiert und JSON-Dateien enthält |
| `docker compose up` schlägt fehl | Image-Build-Fehler | `docker compose build --no-cache` versuchen |
| Alte Anzeigen werden nochmal gemeldet | Neues Volume ohne bisherigen Datenspeicher | Datenspeicher ins Volume kopieren (siehe Server-Einrichtung) |

### Manuelle Installation

**Läuft der Scraper überhaupt?**

**1. Cronjobs prüfen:**

```sh
# Sind die Cronjobs eingerichtet?
crontab -l

# Werden sie ausgeführt?
sudo grep ek-scraper /var/log/syslog | tail -20
```

**2. Datenspeicher prüfen:**

```sh
# Wann wurde zuletzt geschrieben?
ls -la ~/ek-scraper/datastore*.json
```

Wenn das Änderungsdatum weit zurückliegt, aber die Cronjobs laut Syslog laufen, scheitert der Scraper still (siehe nächster Punkt).

**3. Manueller Testlauf mit Debug-Output:**

```sh
ek-scraper --verbose run --data-store datastore.json config.json
```

> **Hinweis:** `--verbose` muss **vor** dem Subcommand `run` stehen.

### Häufige Probleme

| Problem | Ursache | Lösung |
|---------|---------|--------|
| Cronjob läuft, aber Datenspeicher wird nicht aktualisiert | Cron findet `ek-scraper` nicht (eingeschränkter `PATH`) | Vollen Pfad verwenden: `/home/user/.local/bin/ek-scraper` (ermitteln mit `which ek-scraper`) |
| Cronjob-Fehler nicht sichtbar | stdout/stderr werden nicht erfasst | `>> ~/ek-scraper.log 2>&1` an die Crontab-Zeile anhängen |
| Scraper findet keine Anzeigen | Chromium/Playwright veraltet oder kaputt | `playwright install chromium` erneut ausführen |
| Scraper findet Anzeigen, aber keine Benachrichtigungen | Filter zu streng — alle Anzeigen werden rausgefiltert | Im `--verbose`-Output nach `does not match required pattern` suchen und Filter in der Config lockern |
| IP-Sperre durch kleinanzeigen.de | Zu häufige Abfragen | Intervall auf mindestens 15–30 Minuten erhöhen |
| Telegram-Benachrichtigung kommt nicht an | Bot-Token oder Chat-ID falsch | Token und Chat-ID in der Config prüfen, Bot muss der Gruppe hinzugefügt sein |

### Filter debuggen

Im `--verbose`-Modus zeigt der Scraper für jede gefilterte Anzeige den Grund an:

```
scraper: Ad '3373532998' 'Ryzen 5950x rtx 3080 ti Gaming pc'
  does not match required pattern '(?i)(48\s*gb|64\s*gb|...)'
```

Das bedeutet: Die Anzeige wurde gefunden, aber der `require_all_patterns`-Filter hat sie ausgeschlossen. Wenn zu wenige Ergebnisse durchkommen, die Filter-Patterns in der Config anpassen.

### Datenspeicher aufräumen

Wenn der Datenspeicher zu groß wird oder du Benachrichtigungen für bereits gesehene Anzeigen erneut erhalten möchtest:

```sh
# Veraltete Anzeigen entfernen (die nicht mehr in den Suchergebnissen sind)
ek-scraper prune --data-store datastore.json config.json

# Komplett neu starten (alle aktuellen Anzeigen werden als "neu" erkannt)
echo '{}' > datastore.json
ek-scraper run --no-notifications --data-store datastore.json config.json
```

## Funktionsweise

```
Konfigurationsdatei (JSON)
        │
        ▼
┌─────────────────────┐
│  Suchen (parallel)  │
│                     │
│  Playwright startet │
│  Headless Chromium  │──▶ kleinanzeigen.de
│                     │◀── HTML (mit JS gerendert)
│  BeautifulSoup      │
│  parst die Anzeigen │
│                     │
│  Pagination:        │
│  Alle Seiten auto-  │
│  matisch abarbeiten │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Filter anwenden    │
│  • Top-Ads          │
│  • Regex-Muster     │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Datenspeicher      │
│  prüfen             │──▶ Bekannte Anzeigen überspringen
└─────────┬───────────┘
          │ nur neue Anzeigen
          ▼
┌─────────────────────┐
│  Benachrichtigungen │
│  • Telegram         │
│  • Pushover         │
│  • ntfy.sh          │
└─────────────────────┘
```

## Datenspeicher

Der Datenspeicher ist eine JSON-Datei, die alle bereits gesehenen Anzeigen enthält. So wird sichergestellt, dass nur neue Anzeigen Benachrichtigungen auslösen.

- **Standardpfad:** `~/ek-scraper-datastore.json`
- **Format:** JSON mit Anzeigen-IDs als Schlüssel
- **Pruning:** Mit `--prune` oder dem `prune`-Befehl können Anzeigen entfernt werden, die nicht mehr in den Suchergebnissen erscheinen

## Entwicklung

### Repository klonen und einrichten

```sh
git clone git@github.com:jonasehrlich/ek-scraper.git
cd ek-scraper
uv sync
playwright install chromium
```

### Linting und Typprüfung

```sh
uv run ruff check ek_scraper/
uv run mypy ek_scraper/
uv run isort --check ek_scraper/
```

## Lizenz

MIT
