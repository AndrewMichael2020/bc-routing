#!/usr/bin/env python3
# ...existing code...
"""
Check which OSM tags OSMnx preserves and optionally inspect a fetched graph's edge attributes.
"""
import argparse
import sys
import traceback

import osmnx as ox
from map_tool import configure_osmnx


EXPECTED_TAGS = [
    "highway", "name", "ref",
    "surface", "smoothness", "tracktype", "4wd_only", "condition",
    "access", "service", "motor_vehicle", "vehicle", "foot", "bicycle", "horse", "barrier",
    "lanes", "width", "maxspeed", "oneway", "bridge", "tunnel",
    "sidewalk", "cycleway", "shoulder", "lit",
]

def print_settings_tags():
    way = list(getattr(ox.settings, "useful_tags_way", []))
    node = list(getattr(ox.settings, "useful_tags_node", []))
    relation = list(getattr(ox.settings, "useful_tags_relation", []))

    print(f"OSMnx settings.useful_tags_way ({len(way)}):")
    print(", ".join(way))
    print(f"\nOSMnx settings.useful_tags_node ({len(node)}):")
    print(", ".join(node))
    # Some OSMnx versions don't expose useful_tags_relation; guard accordingly
    print(f"\nOSMnx settings.useful_tags_relation ({len(relation)}):")
    if relation:
        print(", ".join(relation))
    else:
        print("(not available in this OSMnx version)")


def check_expected_in_settings():
    way_tags = set(ox.settings.useful_tags_way)
    missing = [t for t in EXPECTED_TAGS if t not in way_tags]
    present = [t for t in EXPECTED_TAGS if t in way_tags]
    print("\nExpected tags present in settings.useful_tags_way:")
    print(", ".join(sorted(present)))
    if missing:
        print("\nExpected tags MISSING from settings.useful_tags_way:")
        print(", ".join(sorted(missing)))
    else:
        print("\nAll expected tags are present in settings.useful_tags_way.")


def inspect_graph(place):
    print("\nAttempting to fetch graph for place: {!r}".format(place))
    try:
        G = ox.graph_from_place(place, network_type="all_private")
    except Exception as e:
        print("Failed to fetch graph (network required):", e)
        traceback.print_exc(limit=1)
        return

    # collect all edge data keys
    edge_keys = set()
    for u, v, k, data in G.edges(keys=True, data=True):
        edge_keys.update(data.keys())

    print("\nNumber of edges in graph:", G.number_of_edges())
    print("Sample edge attribute keys ({} total):".format(len(edge_keys)))
    print(", ".join(sorted(edge_keys)))

    present = [t for t in EXPECTED_TAGS if t in edge_keys]
    missing = [t for t in EXPECTED_TAGS if t not in edge_keys]
    print("\nExpected tags present on fetched graph edges:")
    print(", ".join(sorted(present)))
    if missing:
        print("\nExpected tags NOT found on fetched graph edges (may simply be absent in that area):")
        print(", ".join(sorted(missing)))


def main():
    p = argparse.ArgumentParser(description="Inspect OSMnx preserved tags and optionally graph edge keys")
    p.add_argument("--place", "-p", help="Optional place name to fetch (requires network)")
    args = p.parse_args()

    # Configure OSMnx the same way `map_tool.fetch` does so the
    # `useful_tags_way` list reflects the extra tags we expect to preserve.
    try:
        configure_osmnx({}, timeout=180, memory=1073741824)
    except Exception:
        # best-effort: if configure fails, continue and show current settings
        pass

    print_settings_tags()
    check_expected_in_settings()

    if args.place:
        inspect_graph(args.place)


if __name__ == "__main__":
    main()