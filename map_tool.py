#!/usr/bin/env python3
"""
CLI Tool for Rich Street-Network Extraction with OSMnx + Local Incremental Storage.

This tool provides a command-line interface for extracting detailed street-network
data from OpenStreetMap using OSMnx, with support for local incremental storage.

Usage:
    python map_tool.py fetch "<PLACE_NAME>" --output-dir path/to/data
    python map_tool.py merge --folder path/to/data --output path/to/master.graphml
    python map_tool.py stats path/to/network.graphml
"""

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import networkx as nx
import osmnx as ox

# =============================================================================
# Constants
# =============================================================================

# Extra OSM way tags to preserve beyond OSMnx defaults
EXTRA_USEFUL_TAGS = [
    # Core classification / geometry
    "highway",
    "name",
    "ref",
    # Surface / roughness / wilderness
    "surface",
    "smoothness",
    "tracktype",
    "4wd_only",
    "surface:note",
    "condition",
    # Access / legal / usage
    "access",
    "service",
    "motor_vehicle",
    "vehicle",
    "foot",
    "bicycle",
    "horse",
    "barrier",
    # Physical specifications
    "lanes",
    "width",
    "est_width",
    "maxspeed",
    "maxspeed:practical",
    "oneway",
    "bridge",
    "tunnel",
    # Side facilities / context
    "sidewalk",
    "cycleway",
    "shoulder",
    "lit",
]

# Custom Overpass filter for comprehensive road coverage
CUSTOM_FILTER = (
    '["highway"~"motorway|motorway_link|trunk|trunk_link|primary|primary_link|'
    "secondary|secondary_link|tertiary|tertiary_link|"
    'unclassified|residential|service|track"]'
)

# Set of paved surface types
PAVED_SURFACES = {
    "paved",
    "asphalt",
    "concrete",
    "concrete:plates",
    "concrete:lanes",
    "paving_stones",
    "sett",
    "metal",
    "wood",
}

# Default configuration values
DEFAULT_CONFIG = {
    "overpass_timeout": 180,
    "overpass_memory": 1073741824,
    "overpass_endpoint": None,
    "data_root": "./data",
    "extra_useful_tags": [],
}

# =============================================================================
# Logging Setup
# =============================================================================


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the CLI tool."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


# =============================================================================
# Configuration
# =============================================================================


def load_config(config_path: Path | None = None) -> dict:
    """
    Load configuration from JSON file if it exists.

    Args:
        config_path: Optional path to config file. If None, looks for config.json
                     in the script directory.

    Returns:
        Configuration dictionary merged with defaults.
    """
    config = DEFAULT_CONFIG.copy()

    # Look for config file
    if config_path is None:
        script_dir = Path(__file__).parent
        config_path = script_dir / "config.json"

    if config_path.exists():
        logging.debug(f"Loading config from {config_path}")
        with open(config_path, "r") as f:
            user_config = json.load(f)
        config.update(user_config)

    return config


def configure_osmnx(
    config: dict,
    timeout: int | None = None,
    memory: int | None = None,
) -> None:
    """
    Configure OSMnx settings for rich edge attributes and Overpass settings.

    Args:
        config: Configuration dictionary.
        timeout: Override timeout in seconds.
        memory: Override memory in bytes.
    """
    # Augment useful_tags_way with extra tags
    existing_tags = list(ox.settings.useful_tags_way)
    extra_tags = EXTRA_USEFUL_TAGS + config.get("extra_useful_tags", [])
    all_tags = list(set(existing_tags + extra_tags))
    ox.settings.useful_tags_way = all_tags
    logging.debug(f"Configured {len(all_tags)} useful_tags_way")

    # Configure Overpass settings
    ox.settings.timeout = timeout or config.get("overpass_timeout", 180)
    ox.settings.memory = memory or config.get("overpass_memory", 1073741824)

    # Optionally override Overpass endpoint
    endpoint = config.get("overpass_endpoint")
    if endpoint:
        ox.settings.overpass_endpoint = endpoint
        logging.debug(f"Using custom Overpass endpoint: {endpoint}")


# =============================================================================
# Utility Functions
# =============================================================================


def sanitize_place_name(place_name: str) -> str:
    """
    Convert place name to a filesystem-safe slug.

    Args:
        place_name: Full place name (e.g., "Langley, British Columbia, Canada")

    Returns:
        Sanitized slug (e.g., "Langley_BC")
    """
    # Take first part before first comma and any province/state abbreviation
    parts = [p.strip() for p in place_name.split(",")]

    if len(parts) >= 2:
        # Try to create an abbreviation from second part
        second = parts[1].strip()
        # Check for "British Columbia" -> "BC" style
        words = second.split()
        if len(words) >= 2:
            abbrev = "".join(w[0].upper() for w in words if w[0].isupper() or w[0].islower())
            slug = f"{parts[0]}_{abbrev}"
        else:
            slug = f"{parts[0]}_{second[:2].upper()}"
    else:
        slug = parts[0]

    # Remove non-alphanumeric characters except underscore
    slug = re.sub(r"[^a-zA-Z0-9_]", "", slug.replace(" ", "_"))
    return slug


def get_output_filepath(
    place_name: str,
    output_dir: Path,
    output_name: str | None = None,
    date: str | None = None,
) -> Path:
    """
    Generate the output filepath for a GraphML file.

    Args:
        place_name: Full place name.
        output_dir: Output directory path.
        output_name: Optional custom filename.
        date: Optional date string (YYYY-MM-DD).

    Returns:
        Full path to the output file.
    """
    if output_name:
        return output_dir / output_name

    # Generate default name: PLACE_SLUG__YYYYMMDD.graphml
    place_slug = sanitize_place_name(place_name)
    if date:
        date_str = date.replace("-", "")
    else:
        date_str = datetime.now().strftime("%Y%m%d")

    filename = f"{place_slug}__{date_str}.graphml"
    return output_dir / filename


def calculate_edge_length_km(graph: nx.MultiDiGraph, filter_func) -> float:
    """
    Calculate total length in km for edges matching a filter function.

    Args:
        graph: NetworkX MultiDiGraph with edge attributes.
        filter_func: Function that takes edge data dict and returns bool.

    Returns:
        Total length in kilometers.
    """
    total_meters = 0.0
    for u, v, data in graph.edges(data=True):
        if filter_func(data):
            total_meters += data.get("length", 0)
    return total_meters / 1000.0


# =============================================================================
# Fetch Command
# =============================================================================


def fetch_network(
    place_name: str,
    output_dir: Path,
    output_name: str | None = None,
    date: str | None = None,
    timeout: int = 180,
    memory: int = 1073741824,
    retry: int = 3,
    sleep_seconds: int = 60,
    config: dict | None = None,
) -> int:
    """
    Fetch street network for a place and save as GraphML.

    Args:
        place_name: Place name for OSMnx query.
        output_dir: Directory to save the output file.
        output_name: Optional custom output filename.
        date: Optional date string (YYYY-MM-DD).
        timeout: Overpass timeout in seconds.
        memory: Overpass memory in bytes.
        retry: Number of retries on failure.
        sleep_seconds: Seconds to wait between retries.
        config: Configuration dictionary.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    if config is None:
        config = DEFAULT_CONFIG.copy()

    # Configure OSMnx
    configure_osmnx(config, timeout=timeout, memory=memory)

    # Ensure output directory exists
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Attempt to fetch the graph with retries
    graph = None
    last_error = None

    for attempt in range(1, retry + 1):
        try:
            logging.info(f"Fetching network for '{place_name}' (attempt {attempt}/{retry})")
            graph = ox.graph_from_place(
                place_name,
                custom_filter=CUSTOM_FILTER,
                retain_all=True,
                truncate_by_edge=True,
            )
            logging.info(f"Successfully fetched graph with {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
            break
        except Exception as e:
            last_error = e
            logging.warning(f"Attempt {attempt} failed: {e}")
            if attempt < retry:
                logging.info(f"Waiting {sleep_seconds} seconds before retry...")
                time.sleep(sleep_seconds)

    if graph is None:
        logging.error(
            f"Overpass request failed after {retry} retries. "
            "Please wait and run the same command again."
        )
        logging.error(f"Last error: {last_error}")
        return 1

    # Post-processing: add speeds and travel times
    logging.info("Adding edge speeds and travel times...")
    try:
        graph = ox.add_edge_speeds(graph)
        graph = ox.add_edge_travel_times(graph)
    except Exception as e:
        logging.warning(f"Could not add speeds/travel times: {e}")

    # Add metadata to graph
    fetch_date = date or datetime.now().strftime("%Y-%m-%d")
    graph.graph["source_place"] = place_name
    graph.graph["fetched_at"] = datetime.now().isoformat()
    graph.graph["osmnx_version"] = ox.__version__
    graph.graph["custom_filter"] = CUSTOM_FILTER

    # Add date_fetched to all edges
    for u, v, key, data in graph.edges(keys=True, data=True):
        data["date_fetched"] = fetch_date

    # Determine output filepath
    filepath = get_output_filepath(place_name, output_dir, output_name, date)

    # Save to GraphML
    logging.info(f"Saving graph to {filepath}")
    ox.save_graphml(graph, filepath)

    # Print summary stats
    print_fetch_summary(graph)

    logging.info("Fetch completed successfully.")
    return 0


def print_fetch_summary(graph: nx.MultiDiGraph) -> None:
    """Print summary statistics after a fetch operation."""
    print("\n" + "=" * 60)
    print("FETCH SUMMARY")
    print("=" * 60)

    total_nodes = graph.number_of_nodes()
    total_edges = graph.number_of_edges()
    print(f"Total nodes: {total_nodes:,}")
    print(f"Total edges: {total_edges:,}")

    # Calculate lengths for different categories
    def is_paved(data):
        surface = data.get("surface", "")
        return surface in PAVED_SURFACES

    def is_unpaved(data):
        surface = data.get("surface")
        return surface is not None and surface not in PAVED_SURFACES

    def is_track(data):
        return data.get("highway") == "track"

    def is_alley(data):
        return data.get("service") == "alley"

    paved_km = calculate_edge_length_km(graph, is_paved)
    unpaved_km = calculate_edge_length_km(graph, is_unpaved)
    track_km = calculate_edge_length_km(graph, is_track)
    alley_km = calculate_edge_length_km(graph, is_alley)
    total_km = calculate_edge_length_km(graph, lambda _: True)

    print(f"\nEdge lengths:")
    print(f"  Total:   {total_km:,.2f} km")
    print(f"  Paved:   {paved_km:,.2f} km")
    print(f"  Unpaved: {unpaved_km:,.2f} km")
    print(f"  Tracks:  {track_km:,.2f} km")
    print(f"  Alleys:  {alley_km:,.2f} km")
    print("=" * 60 + "\n")


# =============================================================================
# Merge Command
# =============================================================================


def merge_graphs(
    folder: Path,
    output: Path,
) -> int:
    """
    Merge multiple GraphML files into a single graph.

    Args:
        folder: Directory containing GraphML files.
        output: Output path for merged graph.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    folder = Path(folder)
    output = Path(output)

    # Find all GraphML files
    graphml_files = list(folder.glob("*.graphml"))
    if not graphml_files:
        logging.error(f"No .graphml files found in {folder}")
        return 1

    logging.info(f"Found {len(graphml_files)} GraphML files to merge")

    # Load and merge graphs
    g_total = None
    source_files = []

    for filepath in graphml_files:
        logging.info(f"Loading {filepath.name}...")
        try:
            g_new = ox.load_graphml(filepath)
            source_files.append(filepath.name)

            if g_total is None:
                g_total = g_new
            else:
                g_total = nx.compose(g_total, g_new)

        except Exception as e:
            logging.error(f"Failed to load {filepath}: {e}")
            return 1

    if g_total is None:
        logging.error("No graphs were loaded")
        return 1

    # Add metadata
    g_total.graph["source_files"] = source_files
    g_total.graph["merged_at"] = datetime.now().isoformat()

    # Ensure output directory exists
    output.parent.mkdir(parents=True, exist_ok=True)

    # Save merged graph
    logging.info(f"Saving merged graph to {output}")
    ox.save_graphml(g_total, output)

    logging.info(
        f"Merge completed: {g_total.number_of_nodes():,} nodes, "
        f"{g_total.number_of_edges():,} edges"
    )
    return 0


# =============================================================================
# Stats Command
# =============================================================================


def calculate_stats(filepath: Path) -> int:
    """
    Calculate and print statistics for a GraphML network file.

    Args:
        filepath: Path to GraphML file.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    filepath = Path(filepath)

    if not filepath.exists():
        logging.error(f"File not found: {filepath}")
        return 1

    logging.info(f"Loading graph from {filepath}")
    try:
        graph = ox.load_graphml(filepath)
    except Exception as e:
        logging.error(f"Failed to load graph: {e}")
        return 1

    # Define filter functions
    def is_alley(data):
        return data.get("service") == "alley"

    def is_track(data):
        return data.get("highway") == "track"

    def is_private(data):
        return data.get("access") == "private"

    def is_unpaved(data):
        surface = data.get("surface")
        return surface is not None and surface not in PAVED_SURFACES

    # Calculate totals
    alley_km = calculate_edge_length_km(graph, is_alley)
    track_km = calculate_edge_length_km(graph, is_track)
    private_km = calculate_edge_length_km(graph, is_private)
    unpaved_km = calculate_edge_length_km(graph, is_unpaved)
    total_km = calculate_edge_length_km(graph, lambda _: True)

    # Calculate tracktype histogram
    tracktype_counts = {"grade1": 0, "grade2": 0, "grade3": 0, "grade4": 0, "grade5": 0}
    for u, v, data in graph.edges(data=True):
        if data.get("highway") == "track":
            tracktype = data.get("tracktype", "unknown")
            if tracktype in tracktype_counts:
                tracktype_counts[tracktype] += 1

    # Print results
    print("\n" + "=" * 60)
    print("NETWORK STATISTICS")
    print("=" * 60)
    print(f"File: {filepath.name}")
    print(f"Total nodes: {graph.number_of_nodes():,}")
    print(f"Total edges: {graph.number_of_edges():,}")
    print(f"Total length: {total_km:,.2f} km")
    print()
    print("Road Type Lengths (km):")
    print("-" * 40)
    print(f"  {'Category':<25} {'Length (km)':>12}")
    print("-" * 40)
    print(f"  {'Alleys (service=alley)':<25} {alley_km:>12,.2f}")
    print(f"  {'Wilderness tracks':<25} {track_km:>12,.2f}")
    print(f"  {'Private roads':<25} {private_km:>12,.2f}")
    print(f"  {'Unpaved roads':<25} {unpaved_km:>12,.2f}")
    print("-" * 40)
    print()
    print("Tracktype Histogram (highway=track edges):")
    print("-" * 40)
    print(f"  {'Tracktype':<15} {'Count':>10}")
    print("-" * 40)
    for grade, count in sorted(tracktype_counts.items()):
        print(f"  {grade:<15} {count:>10}")
    print("-" * 40)
    print("=" * 60 + "\n")

    return 0


# =============================================================================
# CLI Argument Parser
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI tool."""
    parser = argparse.ArgumentParser(
        description="CLI Tool for Rich Street-Network Extraction with OSMnx",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Fetch a network:
    python map_tool.py fetch "Langley, British Columbia, Canada" --output-dir ./data/raw

  Merge networks:
    python map_tool.py merge --folder ./data/raw --output ./data/master/merged.graphml

  Show statistics:
    python map_tool.py stats ./data/raw/Langley_BC__20241201.graphml
        """,
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration JSON file",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Fetch command
    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch street network for a place",
    )
    fetch_parser.add_argument(
        "place_name",
        help="Place name for OSMnx query (e.g., 'Langley, British Columbia, Canada')",
    )
    fetch_parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to save the output file",
    )
    fetch_parser.add_argument(
        "--output-name",
        help="Custom output filename (default: PLACE_SLUG__YYYYMMDD.graphml)",
    )
    fetch_parser.add_argument(
        "--date",
        help="Date for the fetch (YYYY-MM-DD format, default: today)",
    )
    fetch_parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Overpass timeout in seconds (default: 180)",
    )
    fetch_parser.add_argument(
        "--memory",
        type=int,
        default=1073741824,
        help="Overpass memory in bytes (default: 1073741824)",
    )
    fetch_parser.add_argument(
        "--retry",
        type=int,
        default=3,
        help="Number of retries on failure (default: 3)",
    )
    fetch_parser.add_argument(
        "--sleep-seconds",
        type=int,
        default=60,
        help="Seconds to wait between retries (default: 60)",
    )

    # Merge command
    merge_parser = subparsers.add_parser(
        "merge",
        help="Merge multiple GraphML files into one",
    )
    merge_parser.add_argument(
        "--folder",
        type=Path,
        required=True,
        help="Directory containing GraphML files to merge",
    )
    merge_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for merged graph",
    )

    # Stats command
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show statistics for a network file",
    )
    stats_parser.add_argument(
        "filepath",
        type=Path,
        help="Path to GraphML file",
    )

    return parser


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> int:
    """Main entry point for the CLI tool."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose)

    # Load configuration
    config = load_config(args.config)

    # Dispatch to appropriate command
    if args.command == "fetch":
        return fetch_network(
            place_name=args.place_name,
            output_dir=args.output_dir,
            output_name=args.output_name,
            date=args.date,
            timeout=args.timeout,
            memory=args.memory,
            retry=args.retry,
            sleep_seconds=args.sleep_seconds,
            config=config,
        )
    elif args.command == "merge":
        return merge_graphs(
            folder=args.folder,
            output=args.output,
        )
    elif args.command == "stats":
        return calculate_stats(
            filepath=args.filepath,
        )
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
