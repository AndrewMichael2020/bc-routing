# CLI Tool for Rich Street-Network Extraction

This tool provides a command-line interface for extracting detailed street-network data using [OSMnx](https://github.com/gboeing/osmnx), with support for fast, local incremental storage.

## Features

- Extract street-network data from OpenStreetMap using OSMnx.
- Save results locally with incremental updates.
- Designed for batch and single-location workflows.

## Installation

```
pip install -r requirements.txt
```

## Usage

```
python cli.py --location "City, Country" --output data/
```

See `cli.py --help` for options.

## Requirements

- Python 3.7+
- OSMnx

## License

MIT