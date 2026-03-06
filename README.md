# Kartencrop

Modulare Werkzeuge zum Erstellen, Kombinieren und Croppen grosser Kartenbilder aus mehreren Kartendiensten.

## Setup

```bash
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Oder als Paket im Entwicklungsmodus:

```bash
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Danach steht auch der Console-Entrypoint zur Verfuegung:

```bash
kartencrop --help
```

## Struktur

- `kartencrop/providers.py`: Tile-Provider fuer OpenFlightMaps, GeoPF, OpenAIP und Basiskarten
- `kartencrop/swissgeo.py`: GeoAdmin-WMS-Helfer fuer die Schweiz
- `kartencrop/tiles.py`: Bounds, Stitching und Preview-Speicherung
- `kartencrop/crop.py`: Cropping-Helfer
- `kartencrop/cli.py`: Zentrale CLI
- `kartencrop/http.py`: HTTP-Helfer fuer Experimente
- `kartencrop/openaip.py`: Gemeinsame OpenAIP-Requests
- `kartencrop/ui_models.py`: Typisierte UI-Konfigurationen fuer OFM, GeoPF, Swiss und OpenAIP
- `kartencrop/cache.py`: Persistenter Tile-Disk-Cache fuer UI und CLI
- `docs/openaip_api/`: lokal gespeicherte OpenAIP-Referenzdoku
- `outputs/generated/`: Standardziel der Streamlit-UI
- `outputs/samples/`: abgelegte Beispielbilder und alte Render-Artefakte
- `outputs/smoke/`: Smoke-Test-Ausgaben
- `outputs/cache/tiles/`: lokaler Tile-Cache fuer wiederholte Vorschau- und Build-Laeufe
- `experiments/`: fruehere Test- und Diagnoseskripte
- `legacy/`: alte Wrapper-Skripte

## CLI-Beispiele

```bash
python -m kartencrop.cli ofm-full --zoom 8 --start-x 144 --start-y 72 --output openflightmaps_finland_z8_full.jpg
python -m kartencrop.cli ofm-composite-full --zoom 8 --start-x 144 --start-y 72 --output openflightmaps_finland_base_aero.png
python -m kartencrop.cli ofm-bbox --zoom 8 --lat-min 35 --lon-min -10 --lat-max 62 --lon-max 25 --chart-type aero --output ofm_europe_bbox.png
python -m kartencrop.cli ofm-composite-bbox --zoom 8 --lat-min 35 --lon-min -10 --lat-max 62 --lon-max 25 --output ofm_europe_composite_bbox.png
python -m kartencrop.cli ofm-probe --zoom 8 --x 129 --y 90 --output probe.png
python -m kartencrop.cli geopf-full --tilematrix 11 --start-col 1025 --start-row 721 --output france_aviation_map_full.jpg
python -m kartencrop.cli geopf-center --tilematrix 11 --lat 46.227638 --lon 2.213749 --radius 2 --output france_aviation_map_center.jpg
python -m kartencrop.cli geopf-bbox --tilematrix 11 --lat-min 45.8 --lon-min 1.6 --lat-max 46.6 --lon-max 2.8 --output france_aviation_map_bbox.jpg
python -m kartencrop.cli swiss-wms --preset wanderkarte --center-lat 46.95108 --center-lon 7.43864 --span-x 10000 --span-y 10000 --output schweizer_wanderkarte.png
python -m kartencrop.cli swiss-wms --preset wanderkarte --center-lat 46.95108 --center-lon 7.43864 --span-x 10000 --span-y 10000 --include-closures --identify-closures --identify-output sperrungen.json --output schweizer_wanderkarte_mit_sperrungen.png
python -m kartencrop.cli openaip-png-probe --zoom 8 --x 134 --y 84 --layer openaip --output openaip_probe.png
python -m kartencrop.cli openaip-png-full --zoom 8 --start-x 134 --start-y 84 --layer hotspots --output openaip_hotspots.png
python -m kartencrop.cli openaip-composite-full --zoom 9 --start-x 270 --start-y 170 --layer openaip --output openaip_composite.png
python -m kartencrop.cli openaip-style --style openaip-default-style --output openaip-default-style.json
python -m kartencrop.cli latlon-to-tile --lat 51.5413 --lon 9.9158 --zoom 12
python -m kartencrop.cli bbox-to-tiles --lat-min 51.4 --lon-min 9.7 --lat-max 51.8 --lon-max 10.2 --zoom 12
python -m kartencrop.cli openaip-vector-grid --zoom 12 --start-x 2160 --start-y 1360 --width 3 --height 3 --layers airports,airspaces,navaids,reporting_points,obstacles,rc_airfields --output openaip_vector_grid.png
python -m kartencrop.cli crop-percent --image openflightmaps_finland_z8_full.jpg --width-pct 25 --height-pct 25
python -m kartencrop.cli crop-regions --image openflightmaps_finland_z8_full.jpg --regions "100,100,400,400;500,200,900,650"
```

## Hinweise

- OpenFlightMaps hat eine unregelmaessige regionale Abdeckung mit internen Luecken. Fuer groessere Ausschnitte ist `ofm-bbox` meist robuster als reine Grenzsuche.
- `ofm-composite-full` und `ofm-composite-bbox` legen die transparente `aero`-Karte auf die `base`-Grundkarte.
- GeoPF SCAN-OACI ist auf Frankreich fokussiert und unterstuetzt jetzt sowohl technische Start-Spalten/Zeilen als auch `GPS-Mittelpunkt` und `geographischen Rahmen`.
- `swiss-wms` schneidet GeoAdmin WMS serverseitig per `BBOX` in `EPSG:2056` aus. Das Standard-Preset ist die Schweizer Wanderkarte.
- Optional kann `swiss-wms` den offiziellen ASTRA-Layer `ch.astra.wanderland-sperrungen_umleitungen` einblenden und Sperrungsdetails per GeoAdmin-REST-API am Kartenmittelpunkt abfragen.
- OpenAIP-Vektortiles unterstuetzen API-Key-Auth per `x-openaip-api-key` Header und `apiKey` Query-Parameter.
- OpenAIP Tiles API unterstuetzt:
  - `GET /data/openaip/{z}/{x}/{y}.pbf` (vector)
  - `GET /data/{openaip|hotspots}/{z}/{x}/{y}.png` (raster)
  - `GET /styles/{openaip-default-style|openaip-satellite-style}.json`
- `openaip-composite-full` mischt OpenAIP mit einer ESRI-Basiskarte, damit Regionen und Topografie lesbar bleiben.
- Wiederholte Tile-Abfragen werden lokal unter `outputs/cache/tiles/` zwischengespeichert.
- HTTP-Anfragen an externe Provider verwenden einen einfachen Retry-/Backoff-Pfad fuer `429` und `5xx`.
- Grosse Tile-Mosaike werden beim Speichern automatisch ueber einen speicherschonenden Renderpfad aufgebaut, damit UI und CLI bei grossen Karten nicht das komplette Endbild nur im RAM halten muessen.
- Die Streamlit-UI speichert letzte Quelle, Presets und Eingaben lokal unter `outputs/config/ui_state.json` und stellt sie beim naechsten Start wieder her.
- In der Seitenleiste kann die lokal gespeicherte UI-Konfiguration mit einem Reset-Button wieder auf die Projekt-Defaults zurueckgesetzt werden.
- GeoPF liest die Tile-Grenzen bevorzugt dynamisch aus den WMTS-Capabilities und faellt nur bei Bedarf auf den statischen Projekt-Fallback zurueck.
- Die UI bietet fuer alle kartenbasierten Quellen eine interaktive Rechteckauswahl auf einer Basemap, uebernimmt den gewaehlten Rahmen direkt in die Koordinatenfelder und zeigt Klick-Koordinaten (Breiten-/Laengengrad) direkt aus der Karte an.

OpenAIP-Auth-Beispiel (PowerShell):

```powershell
$env:OPENAIP_API_KEY="your_api_key"
.\.venv\Scripts\python.exe -c "from kartencrop.openaip import openaip_session, fetch_vector_tile; s=openaip_session(); r=fetch_vector_tile(8,134,84,session=s); print(r.status_code, r.content_type, len(r.content))"
```

## UI

Interaktive UI starten:

```bash
.venv\Scripts\python.exe -m streamlit run map_ui.py
```

Die UI speichert neue Ergebnisse standardmaessig unter `outputs/generated/`.

Standalone-Windows-Exe bauen:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File .\scripts\build_standalone_exe.ps1 -Clean
```

Danach liegt die portable Anwendung unter:

```text
dist_portable\KartencropUI\KartencropUI.exe
```

Falls ein alter Ausgabeordner noch gesperrt ist, weicht das Build-Skript automatisch auf einen neuen Ordner wie `dist_portable_YYYYMMDD_HHMMSS\KartencropUI\KartencropUI.exe` aus.

Die Exe startet den lokalen Streamlit-Server selbst und oeffnet die UI automatisch im Browser.

Aktueller UI-Stand:

- Quellen: `OpenFlightMaps`, `GeoPF`, `Schweizer Wanderkarte`, `OpenAIP`
- Hauptmodus: pro Quelle nur noch `Mittelpunkt` oder `Geographischer Rahmen`
- `Expertenmodus`: technische Tile-Eingaben, Diagnoseoptionen und Spezialparameter
- OpenAIP ist in der UI zusammengefasst:
  - `Nur OpenAIP`
  - `OpenAIP mit Regionskarte`
- Schweizer Karte ist im Normalmodus vereinfacht:
  - Ausschnitt als einfache km-Auswahl
  - Ausgabequalitaet statt roher Pixelwerte

## Tests

```bash
.venv\Scripts\python.exe -m pytest -q
```

Mit Paketinstallation:

```bash
.venv\Scripts\python.exe -m pytest -q
```

Optionale Live-Smoke-Tests gegen echte Provider:

```bash
$env:RUN_LIVE_TESTS="1"
$env:OPENAIP_API_KEY="your_api_key"
.venv\Scripts\python.exe -m pytest -q -m live
```

## Legacy-Wrapper

Alte Wrapper liegen jetzt unter `legacy/`:

- `legacy/create_openflightmaps_full.py`
- `legacy/create_full_map.py`
- `legacy/crop_maps.py`

Weitere Diagnose- und Testskripte liegen unter `experiments/`.
