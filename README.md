# CLI Tool for Rich Street-Network Extraction

This tool provides a command-line interface for extracting detailed street-network data from OpenStreetMap using [OSMnx](https://github.com/gboeing/osmnx), with support for local incremental storage.

## Features

- **Rich OSM Attributes**: Captures comprehensive road attributes including surface type, smoothness, tracktype, access restrictions, and more.
- **Local Storage**: Saves networks as GraphML files for easy inspection and reuse.
- **Incremental Updates**: Supports day-by-day network downloads with merge capability.
- **Network Statistics**: Reports on alleys, wilderness tracks, private roads, and unpaved surfaces.
- **Configurable**: Optional JSON configuration file for custom settings.

## Installation

```bash
pip install -r requirements.txt
```

## Requirements

- Python 3.10+
- OSMnx >= 2.0.0

## Usage

The tool provides three subcommands: `fetch`, `merge`, and `stats`.

### Fetch a Street Network

Download street network data for a place:

```bash
python map_tool.py fetch "Langley, British Columbia, Canada" --output-dir ./data/raw
```

```import osmnx as ox

# choose a radius large enough to cover wilderness area (e.g. 10–50 km)
point = (49.38, -121.44)   # example: Alvin-ish / Hope corridor
dist_m = 40000

# custom filter to include tracks, service roads, unclassified, residential etc.
custom_filter = (
  '["highway"~"track|path|service|unclassified|residential|primary|secondary|tertiary|road|bridleway|cycleway"]'
)

G = ox.graph_from_point(point, dist=dist_m, network_type="all", custom_filter=custom_filter, retain_all=True)
ox.save_graphml(G, "data/raw/Wilderness_Alvin__20251204.graphml")```

```import osmnx as ox
place = "Garibaldi Provincial Park, British Columbia, Canada"
gdf = ox.geocode_to_gdf(place)      # gets polygon for many relations
poly = gdf.geometry.iloc[0]

custom_filter = (
  '["highway"~"track|path|service|unclassified|bridleway|cycleway|path|footway"]'
)

G = ox.graph_from_polygon(poly, network_type="all", custom_filter=custom_filter, retain_all=True)
ox.save_graphml(G, "data/raw/Garibaldi_wilderness__20251204.graphml") ```



Options:
- `--output-dir`: Directory to save the output file (required)
- `--output-name`: Custom output filename (default: `PLACE_SLUG__YYYYMMDD.graphml`)
- `--date`: Date for the fetch (YYYY-MM-DD format, default: today)
- `--timeout`: Overpass timeout in seconds (default: 180)
- `--memory`: Overpass memory in bytes (default: 1073741824)
- `--retry`: Number of retries on failure (default: 3)
- `--sleep-seconds`: Seconds to wait between retries (default: 60)

### Merge Multiple Networks

Combine multiple GraphML files into a single network:

```bash
python map_tool.py merge --folder ./data/raw --output ./data/master/merged.graphml
```

### View Network Statistics

Display statistics for a network file:

```bash
python map_tool.py stats ./data/master/merged.graphml
```

Output includes:
- Total lengths (km) for alleys, wilderness tracks, private roads, and unpaved roads
- Tracktype histogram for `highway=track` edges (grade1 through grade5)

## Configuration

Create a `config.json` file in the script directory for custom settings:

```json
{
    "overpass_timeout": 180,
    "overpass_memory": 1073741824,
    "overpass_endpoint": null,
    "data_root": "./data",
    "extra_useful_tags": []
}
```

Or specify a custom config path:

```bash
python map_tool.py --config /path/to/config.json fetch ...
```

## Directory Structure

Recommended layout for incremental storage:

```
./data/
├── raw/
│   └── YYYY/
│       └── MMDD/
│           ├── Langley_BC__YYYYMMDD.graphml
│           └── Surrey_BC__YYYYMMDD.graphml
└── master/
    └── LwrMainland__YYYYMMDD.graphml
```

## OSM Tags Preserved

The tool preserves a rich set of OSM way tags on each edge:

- **Core**: `highway`, `name`, `ref`
- **Surface/Roughness**: `surface`, `smoothness`, `tracktype`, `4wd_only`, `condition`
- **Access**: `access`, `service`, `motor_vehicle`, `vehicle`, `foot`, `bicycle`, `horse`, `barrier`
- **Physical**: `lanes`, `width`, `maxspeed`, `oneway`, `bridge`, `tunnel`
- **Facilities**: `sidewalk`, `cycleway`, `shoulder`, `lit`

## Verbose Mode

Enable debug logging with the `-v` flag:

```bash
python map_tool.py -v fetch "Langley, BC, Canada" --output-dir ./data/raw
```

## License

MIT

## Routing Test Examples

Use the `scripts/generate_nurse_routes.py` tool to run synthetic routing tests against a merged master graph. The script produces a CSV summary and (optionally) an interactive Folium HTML map. It accepts parameters to control the number of nurses, hubs, patients, random seed, and how clustered the nurses/patients should be.

Common flags (examples):

- `--graph PATH` : path to merged graph (GraphML)
- `--nurses N` : number of nurse starting locations
- `--hubs H` : number of hub centers where nurses are clustered
- `--patients P` : number of patient home locations to generate
- `--seed S` : RNG seed for reproducible tests
- `--cluster-radius KM` : (km) radius for clustering patients around hubs. Small values create short, local routes; large values create long, spread-out routes.
- `--output PATH` : CSV summary output
- `--map-output PATH` : optional Folium HTML map output
- `--normalize-speeds` : normalize speeds and recompute `travel_time` using conservative defaults

Examples

- Short/clustered routes (many short visits near hubs):

```bash
python scripts/generate_nurse_routes.py \
  --graph ./data/master/merged.graphml \
  --nurses 30 --hubs 5 --patients 150 \
  --seed 42 --cluster-radius 0.5 \
  --output ./data/routes_summary_clustered.csv \
  --map-output ./data/routes_map_clustered.html
```

- Long/spread routes (wider coverage, longer average trips):

```bash
python scripts/generate_nurse_routes.py \
  --graph ./data/master/merged.graphml \
  --nurses 30 --hubs 5 --patients 150 \
  --seed 42 --cluster-radius 50 \
  --output ./data/routes_summary_spread.csv \
  --map-output ./data/routes_map_spread.html
```

- Single long route test (example: Hope -> Coquitlam):

If you want to test a single origin/destination pair (useful for corridor checks), either pass `--from`/`--to` (if supported) or run a small Python snippet that geocodes and routes using the merged graph:

```python
import osmnx as ox

G = ox.load_graphml('data/master/merged.graphml')
src = (49.3799779, -121.4415851)   # Hope
dst = (49.2842958, -122.793281)    # Coquitlam
u = ox.distance.nearest_nodes(G, src[1], src[0])
v = ox.distance.nearest_nodes(G, dst[1], dst[0])
path = ox.shortest_path(G, u, v, weight='travel_time')
print('nodes:', len(path))

# compute totals
length_m = sum(G.edges[u2, v2, k].get('length', 0) for u2, v2, k in zip(path[:-1], path[1:], [0]*(len(path)-1)))
time_s = sum(G.edges[u2, v2, k].get('travel_time', 0) for u2, v2, k in zip(path[:-1], path[1:], [0]*(len(path)-1)))
print(f'Length (km): {length_m/1000:.2f}, time (min): {time_s/60:.2f}')
```

Statistics reported

The generator prints/per-row outputs for each route and computes aggregate statistics across all routes. Useful summary statistics include:

- minimum, first quartile (Q1), median, mean, third quartile (Q3), and maximum for route `length_km` and `travel_min`.

Performance and memory

- Generating many routes over a large merged graph can be memory and CPU intensive. Use the `--cluster-radius` parameter to control route scale and reduce peak memory by testing with fewer `--patients` first. If you need long corridor tests (e.g., Hope → Coquitlam) make sure the merged graph covers those areas (fetch and merge tiles that include the end points); otherwise nearest-node snapping will produce disconnected results.

If you want, I can add the exact `--cluster-radius` flag implementation into `scripts/generate_nurse_routes.py` (or a `--cluster-mode tight|spread` alternative) — tell me which behavior you prefer and I will patch the script accordingly.