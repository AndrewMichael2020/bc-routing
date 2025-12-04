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
python map_tool.py stats ./data/raw/Langley_BC__20241201.graphml
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