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

## Installation

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

### Benachrichtigungen (`notifications`)

Alle Backends sind optional und können kombiniert werden. Pro Suche wird eine Benachrichtigung gesendet, wenn neue Anzeigen gefunden werden.

#### Telegram

Benachrichtigungen über einen Telegram-Bot.

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

## Regelmäßige Ausführung (Cronjob)

Um `ek-scraper` automatisch regelmäßig auszuführen, richte einen Cronjob ein:

```sh
crontab -e
```

Beispiel — alle 30 Minuten ausführen:

```
*/30 * * * * ek-scraper run --data-store ~/ek-scraper-datastore.json ~/config.json
```

> Führe den Scraper nicht zu häufig aus, um eine IP-Sperre durch kleinanzeigen.de zu vermeiden. Ein Intervall von 15–30 Minuten ist empfehlenswert.

Ein nützliches Tool zur Erstellung von Cron-Ausdrücken: [crontab.guru](https://crontab.guru/)

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
