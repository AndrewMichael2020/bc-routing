#!/usr/bin/env python3
"""Plot Surrey -> Hope corridor on a Folium map using the merged graph.

Outputs an HTML file you can open in a browser to visually inspect
which route the graph is taking between Surrey and Hope.
"""
import sys
from pathlib import Path

import folium
import osmnx as ox


def main():
    graph_path = Path("data/master/merged.graphml")
    if not graph_path.exists():
        print("Graph file not found:", graph_path)
        sys.exit(2)

    print(f"Loading graph from {graph_path}...")
    G = ox.load_graphml(graph_path)

    # Known nodes from your earlier REPL session
    u = 10199121387  # Surrey-ish
    v = 13053107295  # Hope-ish

    print("Computing shortest path (travel_time)...")
    path = ox.shortest_path(G, u, v, weight="travel_time")
    if path is None:
        print("No path found between Surrey node and Hope node.")
        sys.exit(1)

    print("Nodes in path:", len(path))

    # helper to get node lat/lon
    def node_latlon(n):
        nd = G.nodes[n]
        lon = nd.get("x")
        lat = nd.get("y")
        try:
            return float(lat), float(lon)
        except Exception:
            return None

    # build lat/lon sequence for the path
    latlons = []
    for n in path:
        ll = node_latlon(n)
        if ll:
            latlons.append(ll)

    if not latlons:
        print("Could not extract coordinates for path; aborting.")
        sys.exit(1)

    # center map on midpoint of path
    avg_lat = sum(lat for lat, _ in latlons) / len(latlons)
    avg_lon = sum(lon for _, lon in latlons) / len(latlons)

    m = folium.Map(location=[avg_lat, avg_lon], tiles="cartodbpositron", zoom_start=9)

    # add polyline for route
    folium.PolyLine(
        [(lat, lon) for lat, lon in latlons],
        color="red",
        weight=4,
        opacity=0.8,
        tooltip="Surrey -> Hope route",
    ).add_to(m)

    # add markers for origin/destination
    folium.Marker(latlons[0], popup="Surrey origin").add_to(m)
    folium.Marker(latlons[-1], popup="Hope destination").add_to(m)

    out = Path("data/routes_surrey_hope.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(out))
    print(f"Saved Surrey->Hope route map to {out}")


if __name__ == "__main__":
    main()
