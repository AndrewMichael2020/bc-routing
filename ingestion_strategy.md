# Quadrant-Based Ingestion Strategy for OSM Networks

This document describes a **spatial quadrant ingestion strategy** to fetch OSM data via OSMnx/Overpass using tiles (quadrants) instead of administrative boundaries (cities/towns). The goal is to avoid coverage gaps that occur when relying only on place names.

## Why Quadrants Instead of Towns

- **Boundary Gaps**: `graph_from_place` follows administrative polygons that may not include rural roads, connectors, or in-between areas.
- **Corridors / Cross-Town Routes**: Long routes (e.g., inter-city corridors) can cross many town polygons and be partially missing if one polygon is sparse or oddly shaped.
- **Deterministic Coverage**: A fixed tiling (grid of quadrants) guarantees that every location in the study area is covered at least once.

## High-Level Approach

1. **Define Study Area**: Choose a bounding box that covers the full region of interest (e.g., all of BC, or Lower Mainland + key corridors).
2. **Create a Grid**: Split the bounding box into an N×M grid ("quadrants" / tiles). Each cell is a (min_lat, min_lon, max_lat, max_lon) bounding box.
3. **Fetch Per Tile**: For each tile, call OSMnx with a bounding box API (e.g., `graph_from_bbox` or `graph_from_polygon`) using the same `CUSTOM_FILTER` and rich tags as `map_tool.fetch`.
4. **Persist Incrementally**: Save each tile as a GraphML file under `data/raw/tiles/YYYYMMDD/` with systematic names (e.g., `tile_r{row}_c{col}__YYYYMMDD.graphml`).
5. **Merge to Master**: Use `map_tool.py merge` to combine all tile GraphMLs into a single `merged.graphml` in `data/master/`.
6. **Re-run As Needed**: For new dates, repeat the fetch per tile. Old tiles remain as an audit trail; master graphs can be regenerated per date.

## Coordinate / Tiling Design

- **Bounding Box**: Define `min_lat`, `max_lat`, `min_lon`, `max_lon` for the full region.
- **Grid Size**: Choose `rows` and `cols` based on:
  - Overpass limits (more, smaller tiles → safer; fewer, bigger tiles → faster but riskier).
  - Desired spatial resolution for gap analysis.
- **Overlap Margin** (recommended): Add a small buffer (e.g., 0.01° lat/lon) around each tile to avoid cutting roads at boundaries. This means tiles slightly overlap and merge cleanly.

Pseudo-code for grid generation:

```python
import numpy as np

min_lat, max_lat = 48.0, 51.0
min_lon, max_lon = -124.0, -120.0
rows, cols = 6, 6

lats = np.linspace(min_lat, max_lat, rows + 1)
lons = np.linspace(min_lon, max_lon, cols + 1)

for r in range(rows):
    for c in range(cols):
        tile_min_lat = lats[r]
        tile_max_lat = lats[r + 1]
        tile_min_lon = lons[c]
        tile_max_lon = lons[c + 1]
        # optional: expand by a small buffer
        # then call graph_from_bbox or graph_from_polygon
```

## Ingestion Workflow

1. **Generate Tile Definitions**
   - Create a JSON/CSV file describing all tiles:
     - `id`, `row`, `col`, `min_lat`, `max_lat`, `min_lon`, `max_lon`.
   - Store under `data/tiles/tiles_bc_6x6.json` (for example).

2. **Tile Fetch Script** (suggested new script, e.g., `scripts/fetch_tiles.py`)
   - Reads tile definitions and loops over tiles.
   - For each tile:
     - Constructs a safe output name: `Tile_r{row}_c{col}__YYYYMMDD.graphml`.
     - Calls OSMnx with a bbox-based function and `CUSTOM_FILTER`.
     - Respects `overpass_timeout`, `overpass_memory`, and custom endpoint from `config.json`.
     - Sleeps between requests if needed to respect Overpass limits.

3. **Resilience & Caching**
   - **Idempotency**: Before fetching a tile, check if the expected GraphML file already exists; skip to avoid refetching.
   - **Retry Logic**: Implement retries per tile similar to `fetch_network` (e.g., 3 attempts with sleep between).
   - **Logging**: Log success/failure per tile and keep a simple CSV/JSON report of outcomes.

4. **Merge Step**
   - Once all tiles for a date are fetched:

     ```bash
     python map_tool.py merge \
       --folder ./data/raw/tiles/20251204 \
       --output ./data/master/BC_tiles__20251204.graphml
     ```

   - Optionally, run `python map_tool.py stats ./data/master/BC_tiles__20251204.graphml` to verify coverage and road-type stats.

## How This Avoids Missing Data

- **Non-Administrative Areas**: Quadrants cover wilderness, industrial, or unincorporated areas that aren't captured by "city" polygons.
- **Boundary Robustness**: Overlapping tiles ensure roads near edges are included at least once.
- **Deterministic Completeness**: By exhausting all tiles in the grid, you can be confident the entire bounding box was queried.

## Integration with Existing Tools

- **Reuse `configure_osmnx`** from `map_tool.py` to ensure the same `EXTRA_USEFUL_TAGS`, `CUSTOM_FILTER`, and Overpass settings.
- **File Naming**: Keep the existing `YYYYMMDD` convention and store tile outputs under `data/raw/` so they can be merged the same way as town-based files.
- **Backwards Compatibility**: You can continue using town-based `fetch` for ad-hoc pulls (e.g., testing a new city) while tiles handle systematic full-region ingestion.

## Next Steps to Implement

1. Define the bounding box and grid resolution for your region of interest (BC-wide vs Lower Mainland corridor vs specific health regions).
2. Create a tile-definition file under `data/tiles/`.
3. Implement a `scripts/fetch_tiles.py` that:
   - Uses `configure_osmnx` and `CUSTOM_FILTER`.
   - Iterates over tiles, fetches via bbox, and saves GraphML per tile.
4. Add a short section to `README.md` documenting tile-based ingestion and example commands.

Once this is in place, you can treat tile-based master graphs as your canonical, gap-free networks, while town-level graphs remain useful for local debugging and demos.

## Example: 5‑Day Plan for Lower Mainland

Below is a **concrete 5‑day ingestion schedule** to cover the Lower Mainland using existing `map_tool.py fetch` plus a few extra wilderness / corridor tiles. You can tweak place names, dates, and output folders as needed.

### Common Flags/Conventions

- Root data folder: `./data/raw`
- Date string in filenames: use the actual run date (here shown as `20251204`).
- Use `-v` on first runs to see more logs.

> Note: These commands use **place-based fetches** to keep things simple. Once you add a tile-based `fetch_tiles.py`, you can replace or augment these with quadrant tiles (e.g., `LM_Q1`, `LM_Q2`, …).

### Day 1 – Core Metro (Vancouver, Burnaby, New Westminster)

```bash
python map_tool.py -v fetch "Vancouver, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-04

python map_tool.py -v fetch "Burnaby, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-04

python map_tool.py -v fetch "New Westminster, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-04
```

### Day 2 – North Shore + Tri-Cities

```bash
python map_tool.py -v fetch "North Vancouver, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-05

python map_tool.py -v fetch "West Vancouver, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-05

python map_tool.py -v fetch "Coquitlam, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-05

python map_tool.py -v fetch "Port Coquitlam, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-05

python map_tool.py -v fetch "Port Moody, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-05
```

### Day 3 – Surrey / Delta / Richmond

```bash
python map_tool.py -v fetch "Surrey, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-06

python map_tool.py -v fetch "Delta, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-06

python map_tool.py -v fetch "Richmond, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-06
```

### Day 4 – Fraser Valley (Langley, Abbotsford, Chilliwack)

```bash
python map_tool.py -v fetch "Langley, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-07

python map_tool.py -v fetch "Abbotsford, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-07

python map_tool.py -v fetch "Chilliwack, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-07
```

### Day 5 – Connectors / Wilderness Corridors

These are to cover mountain passes, river corridors, and sparsely populated connectors between municipalities.

```bash
# Hope / Coquihalla corridor area
python map_tool.py -v fetch "Hope, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-08

# Sea-to-Sky corridor (Squamish, Whistler) – optional but useful for regional routes
python map_tool.py -v fetch "Squamish, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-08

python map_tool.py -v fetch "Whistler, British Columbia, Canada" \
  --output-dir ./data/raw \
  --date 2025-12-08
```

### After Each 5‑Day Cycle – Merge and Inspect

Once the 5‑day set is complete, you can merge all the new GraphML files into a master Lower Mainland graph and inspect stats:

```bash
python map_tool.py merge \
  --folder ./data/raw \
  --output ./data/master/LowerMainland__20251208.graphml

python map_tool.py stats ./data/master/LowerMainland__20251208.graphml
```

If you later move to **quadrant tiles**, you can keep the same 5‑day cadence (e.g., 20% of tiles per day) and just swap the per-town fetch commands for tile-based fetches.
