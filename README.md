# Kartencrop

Kartencrop ist ein Werkzeug zum Laden, Zusammensetzen und Zuschneiden von Karten aus mehreren Quellen.

Der Schwerpunkt liegt auf:

- `OpenFlightMaps`
- `GeoPF SCAN-OACI`
- `OpenAIP`
- `GeoAdmin WMS` fuer die Schweiz

Das Projekt bietet zwei Wege:

- eine Streamlit-Oberflaeche fuer die interaktive Nutzung
- eine CLI fuer reproduzierbare Laeufe und Skripting

## Funktionen

- Karten aus mehreren Tile- oder WMS-Quellen laden
- ganze Bereiche aus Tiles zusammensetzen
- transparente Overlays kombinieren, z. B. `OpenFlightMaps base + aero`
- OpenAIP auf eine Grundkarte legen
- Karten per Prozent oder per festen Regionen zuschneiden
- Mittelpunkt oder geographischen Rahmen direkt ueber Koordinaten angeben
- lokalen Tile-Cache fuer wiederholte Laeufe nutzen

## Kartenquellen

### OpenFlightMaps

- regionale Abdeckung mit internen Luecken
- `aero` ist transparent
- `base` ist die Grundkarte
- sinnvoll fuer Luftfahrtkarten und Overlays

### GeoPF Frankreich

- SCAN-OACI ueber WMTS
- auf Frankreich begrenzt
- Bereich kann ueber Mittelpunkt oder geographischen Rahmen bestimmt werden

### OpenAIP

- Raster-Tiles und Vector-Tiles
- API-Key erforderlich
- optional mit Grundkarte darunter

### Schweizer Wanderkarte

- GeoAdmin WMS
- serverseitiger Zuschnitt per Bounding Box
- optional mit ASTRA-Sperrungen und Umleitungen

## Voraussetzungen

- Windows 64-Bit
- Python `3.12`
- Internetzugang fuer die Kartenquellen

Fuer `OpenAIP` zusaetzlich:

- gueltiger API-Key

## Installation

Virtuelle Umgebung anlegen und Abhaengigkeiten installieren:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Oder als Paket im Entwicklungsmodus:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Danach stehen zur Verfuegung:

- `kartencrop`
- `kartencrop-ui`

## UI

```powershell
.\.venv\Scripts\python.exe -m streamlit run map_ui.py
```

Oder:

```powershell
kartencrop-ui
```

Standardziel fuer neue Ausgaben:

- `outputs/generated/`

Die UI speichert den letzten lokalen Zustand unter:

- `outputs/config/ui_state.json`

## CLI

Hilfe:

```powershell
kartencrop --help
```

Beispiele:

### OpenFlightMaps

```powershell
kartencrop ofm-bbox --zoom 8 --lat-min 35 --lon-min -10 --lat-max 62 --lon-max 25 --chart-type aero --output ofm_europe.png
kartencrop ofm-composite-bbox --zoom 8 --lat-min 35 --lon-min -10 --lat-max 62 --lon-max 25 --output ofm_europe_composite.png
```

### GeoPF Frankreich

```powershell
kartencrop geopf-center --tilematrix 11 --lat 48.8566 --lon 2.3522 --radius 2 --output geopf_paris.jpg
kartencrop geopf-bbox --tilematrix 11 --lat-min 45.8 --lon-min 1.6 --lat-max 46.6 --lon-max 2.8 --output geopf_bbox.jpg
```

### Schweizer Wanderkarte

```powershell
kartencrop swiss-wms --preset wanderkarte --center-lat 46.4067 --center-lon 8.6047 --span-x 10000 --span-y 10000 --output schweiz.png
```

Mit Sperrungen:

```powershell
kartencrop swiss-wms --preset wanderkarte --center-lat 46.4067 --center-lon 8.6047 --span-x 10000 --span-y 10000 --include-closures --output schweiz_mit_sperrungen.png
```

### OpenAIP

PowerShell:

```powershell
$env:OPENAIP_API_KEY="dein_api_key"
```

Dann z. B.:

```powershell
kartencrop openaip-png-full --zoom 9 --start-x 275 --start-y 167 --layer openaip --output openaip.png
kartencrop openaip-composite-full --zoom 9 --start-x 275 --start-y 167 --layer openaip --output openaip_composite.png
```

### Cropping

```powershell
kartencrop crop-percent --image ofm_europe.png --width-pct 25 --height-pct 25
kartencrop crop-regions --image ofm_europe.png --regions "100,100,400,400;500,200,900,650"
```

## Wichtige Hinweise

- `OpenFlightMaps` hat keine saubere rechteckige Vollabdeckung. Leere Stellen innerhalb eines grossen Bereichs sind normal.
- `GeoPF` ist fachlich und technisch auf Frankreich begrenzt.
- `OpenAIP` benoetigt fuer produktive Nutzung einen API-Key.
- Die UI rundet tilebasierte Rahmen immer auf ganze Tiles. Dadurch kann der effektiv geladene Bereich je nach Detailstufe etwas groesser sein als der eingegebene Koordinatenrahmen.
- Schweizer WMS-Karten haben keinen eigenen Zoomparameter. Der sichtbare Detailgrad entsteht dort aus Bounding Box und Ausgabeaufloesung.

## Aufbau

- `kartencrop/`: Kernpaket
- `map_ui.py`: Streamlit-Einstieg
- `tests/`: Test-Suite
- `scripts/`: Hilfsskripte, u. a. Exe-Build
- `experiments/`: Diagnose- und Testskripte
- `legacy/`: alte Wrapper
- `docs/`: lokale Referenzdateien

Wichtige Module:

- `kartencrop/providers.py`: Kartenquellen
- `kartencrop/tiles.py`: Tile-Rendering und speicherschonendes Speichern
- `kartencrop/cli.py`: CLI
- `kartencrop/swissgeo.py`: GeoAdmin-Helfer
- `kartencrop/ui_render.py`: UI-Konfiguration
- `kartencrop/ui_actions.py`: UI-Aktionen

## Tests

Standard:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Optionale Live-Tests:

```powershell
$env:RUN_LIVE_TESTS="1"
$env:OPENAIP_API_KEY="dein_api_key"
.\.venv\Scripts\python.exe -m pytest -q -m live
```

## Standalone-Exe

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File .\scripts\build_standalone_exe.ps1 -Clean
```

Die Exe liegt danach in einem `dist_portable...`-Ordner, z. B.:

```text
dist_portable_YYYYMMDD_HHMMSS\KartencropUI\KartencropUI.exe
```

Hinweise zur Exe:

- laeuft ohne lokale Python-Installation
- benoetigt weiter Internetzugang
- startet lokal einen Streamlit-Server und oeffnet die Oberflaeche im Browser
- der komplette Exe-Ordner muss zusammenbleiben

## Lizenz und Datenquellen

Die Software in diesem Repository und die einzelnen Kartenquellen sind getrennt zu betrachten.

Vor Nutzung und Weitergabe von Kartenausschnitten solltest du die Bedingungen der jeweiligen Anbieter pruefen:

- OpenFlightMaps
- GeoPF / IGN France
- OpenAIP
- GeoAdmin / swisstopo / ASTRA

