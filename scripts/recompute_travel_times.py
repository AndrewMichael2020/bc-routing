#!/usr/bin/env python3
"""Recompute edge speeds and travel_time on a merged GraphML graph.

This script loads a GraphML file, normalizes numeric length, recomputes
OSMnx speeds based on highway type, and then sets `travel_time` on every
edge as:

    travel_time = length_m / (speed_kph * 1000/3600)

so all edges have consistent, non-null travel_time suitable for routing.

Usage:
  python scripts/recompute_travel_times.py \
    --input ./data/master/merged.graphml \
    --output ./data/master/merged_with_times.graphml
"""
import argparse
from pathlib import Path

import osmnx as ox


def ensure_numeric_length(G):
    """Ensure edge `length` attributes are numeric floats where present."""
    for u, v, k, data in G.edges(keys=True, data=True):
        if "length" in data:
            try:
                if not isinstance(data["length"], (int, float)):
                    data["length"] = float(data["length"])  # meters
            except Exception:
                # if conversion fails, drop length so OSMnx can recompute if needed
                data.pop("length", None)


def recompute_speeds_and_times(G):
    """Recompute `speed_kph` and `travel_time` on all edges.

    Uses OSMnx's `add_edge_speeds` and `add_edge_travel_times`, then enforces
    the simple relationship travel_time = length / speed.
    """
    # Normalize existing length values first
    ensure_numeric_length(G)

    # Let OSMnx assign default speeds by highway type
    G = ox.add_edge_speeds(G)

    # Ensure numeric speed_kph
    for u, v, k, data in G.edges(keys=True, data=True):
        if "speed_kph" in data:
            try:
                if not isinstance(data["speed_kph"], (int, float)):
                    data["speed_kph"] = float(data["speed_kph"])
            except Exception:
                data.pop("speed_kph", None)

    # Now enforce travel_time = length / speed for all edges with both attrs
    for u, v, k, data in G.edges(keys=True, data=True):
        length_m = data.get("length")
        speed_kph = data.get("speed_kph")
        if isinstance(length_m, (int, float)) and isinstance(speed_kph, (int, float)) and speed_kph > 0:
            # meters / (km/h * 1000/3600) = seconds
            data["travel_time"] = float(length_m) / (speed_kph * 1000.0 / 3600.0)
        else:
            # if we can't compute a sane time, drop it so caller sees it's missing
            data.pop("travel_time", None)

    return G


def main():
    ap = argparse.ArgumentParser(description="Recompute edge travel_time on a GraphML graph")
    ap.add_argument("--input", required=True, help="Input GraphML path")
    ap.add_argument("--output", required=True, help="Output GraphML path")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    if not in_path.exists():
        print("Input graph not found:", in_path)
        raise SystemExit(2)

    print(f"Loading graph from {in_path}...")
    G = ox.load_graphml(in_path)

    print("Recomputing speeds and travel times...")
    G = recompute_speeds_and_times(G)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, out_path)
    print(f"Saved updated graph with travel_time to {out_path}")


if __name__ == "__main__":
    main()
