#!/usr/bin/env python3
"""Generate mock routes for nurses using a merged OSMnx GraphML.

Creates N nurses and assigns M routes each to random patient nodes.
Saves a CSV summary and prints details to stdout.

Usage:
  python scripts/generate_nurse_routes.py --graph ./data/master/merged.graphml \
      --nurses 2 --routes-per 5 --output ./data/routes.csv
"""
import argparse
import csv
import random
import sys
from pathlib import Path

import networkx as nx
import osmnx as ox
try:
    import folium
except Exception:
    folium = None


def ensure_numeric_edge_attrs(G, attrs=("length", "travel_time")):
    """Ensure listed edge attributes are numeric (float) when possible."""
    for u, v, k, data in G.edges(keys=True, data=True):
        for a in attrs:
            if a in data:
                try:
                    # Some GraphML loaders store numbers as strings
                    if not isinstance(data[a], (int, float)):
                        data[a] = float(data[a])
                except Exception:
                    # leave as-is if conversion fails
                    pass


def select_valid_nodes(G, count, min_degree=1, seed=None):
    nodes = [n for n, d in G.degree() if d >= min_degree]
    if seed is not None:
        random.seed(seed)
    if count > len(nodes):
        raise ValueError("Not enough valid nodes to sample")
    return random.sample(nodes, count)


def route_summary(G, path, weight_attr="length"):
    total = 0.0
    for u, v in zip(path[:-1], path[1:]):
        # for MultiDiGraph find an edge between u->v and sum weight
        data = None
        try:
            data = G.get_edge_data(u, v)
        except Exception:
            data = None
        if data:
            # choose the first key
            if isinstance(data, dict):
                # values are keyed by edge-key
                first = next(iter(data.values()))
                val = first.get(weight_attr, 0)
                try:
                    total += float(val)
                except Exception:
                    pass
    return total


def main():
    p = argparse.ArgumentParser(description="Generate mock nurse routes from merged graph")
    p.add_argument("--graph", required=True, help="Path to merged GraphML file")
    p.add_argument("--nurses", type=int, default=2)
    p.add_argument("--routes-per", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", default="./data/routes_summary.csv")
    p.add_argument("--map-output", default="./data/routes_map.html", help="Optional HTML map output (requires folium)")
    args = p.parse_args()

    graph_path = Path(args.graph)
    if not graph_path.exists():
        print("Graph file not found:", graph_path)
        sys.exit(2)

    print(f"Loading graph from {graph_path}...")
    G = ox.load_graphml(graph_path)

    # normalize numeric edge attributes we will use
    ensure_numeric_edge_attrs(G, attrs=("length", "travel_time"))

    # choose weight preference
    weight_attr = "travel_time" if any(
        isinstance(v.get("travel_time"), (int, float)) and v.get("travel_time") > 0
        for _, _, k, v in G.edges(keys=True, data=True)
    ) else "length"

    print(f"Using weight attribute: {weight_attr}")

    random.seed(args.seed)

    # pick nurse home nodes
    nurse_origins = select_valid_nodes(G, args.nurses, seed=args.seed)

    # prepare targets - pick a pool of candidate patient nodes
    candidate_count = args.nurses * args.routes_per * 4
    candidates = select_valid_nodes(G, candidate_count, seed=args.seed + 1)

    rows = []
    route_id = 0
    max_attempts = 1000
    route_paths = []

    for i, origin in enumerate(nurse_origins, start=1):
        assigned = 0
        attempts = 0
        while assigned < args.routes_per and attempts < max_attempts:
            attempts += 1
            dest = random.choice(candidates)
            if dest == origin:
                continue
            try:
                path = nx.shortest_path(G, origin, dest, weight=weight_attr)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue

            # compute metrics
            if weight_attr == "length":
                length_m = route_summary(G, path, weight_attr="length")
                time_sec = route_summary(G, path, weight_attr="travel_time")
            else:
                time_sec = route_summary(G, path, weight_attr="travel_time")
                length_m = route_summary(G, path, weight_attr="length")

            length_km = (length_m or 0.0) / 1000.0
            time_min = (time_sec or 0.0) / 60.0

            route_id += 1
            rows.append({
                "route_id": route_id,
                "nurse_id": f"nurse_{i}",
                "origin": origin,
                "destination": dest,
                "nodes_in_path": len(path),
                "length_km": round(length_km, 3),
                "travel_min": round(time_min, 2),
            })
            # keep the full path for mapping
            route_paths.append((route_id, f"nurse_{i}", path, length_km, time_min))

            print(f"Route {route_id}: nurse_{i} {origin} -> {dest} | {length_km:.3f} km | {time_min:.2f} min")

            assigned += 1

    # write CSV
    outp = Path(args.output)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["route_id", "nurse_id", "origin", "destination", "nodes_in_path", "length_km", "travel_min"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Wrote {len(rows)} routes to {outp}")

    # Generate folium map if requested and folium is available
    map_out = Path(args.map_output)
    if folium is None:
        print("Folium not installed; skipping map generation. To enable, pip install folium")
        return

    if len(route_paths) == 0:
        print("No routes to map")
        return

    # helper to get node lat/lon
    def node_latlon(n):
        nd = G.nodes[n]
        # OSMnx stores lon in 'x' and lat in 'y'
        lon = nd.get("x")
        lat = nd.get("y")
        try:
            return float(lat), float(lon)
        except Exception:
            return None

    # compute map center from used nodes
    used_nodes = set()
    for _, _, path, _, _ in route_paths:
        used_nodes.update(path[:1])
        used_nodes.update(path[-1:])

    coords = [node_latlon(n) for n in used_nodes]
    coords = [c for c in coords if c]
    if not coords:
        print("Could not determine node coordinates; skipping map generation")
        return

    avg_lat = sum(c[0] for c in coords) / len(coords)
    avg_lon = sum(c[1] for c in coords) / len(coords)

    m = folium.Map(location=[avg_lat, avg_lon], tiles="cartodbpositron", zoom_start=12)

    # color palette for nurses
    colors = ["blue", "green", "red", "purple", "orange", "darkred", "cadetblue"]
    nurse_colors = {}

    for rid, nurse_id, path, length_km, time_min in route_paths:
        if nurse_id not in nurse_colors:
            nurse_colors[nurse_id] = colors[len(nurse_colors) % len(colors)]
        color = nurse_colors[nurse_id]

        # convert node path to latlon list
        latlons = []
        for n in path:
            ll = node_latlon(n)
            if ll:
                latlons.append([ll[0], ll[1]])

        if latlons:
            folium.PolyLine(latlons, color=color, weight=4, opacity=0.8,
                            tooltip=f"{nurse_id} route {rid}: {length_km:.2f} km, {time_min:.1f} min").add_to(m)

            # add markers for origin and destination
            folium.CircleMarker(latlons[0], radius=4, color=color, fill=True,
                                popup=f"{nurse_id} origin {rid}").add_to(m)
            folium.Marker(latlons[-1], icon=folium.Icon(color=color),
                          popup=f"{nurse_id} dest {rid}<br>{length_km:.2f} km, {time_min:.1f} min").add_to(m)

    # add simple legend
    legend_html = "<div style='position: fixed; bottom: 50px; left: 50px; z-index:9999; background: white; padding: 8px; border:1px solid #ccc;'>"
    legend_html += "<b>Nurse colors</b><br>"
    for nid, col in nurse_colors.items():
        legend_html += f"<span style='display:inline-block;width:12px;height:12px;background:{col};margin-right:6px;'></span>{nid}<br>"
    legend_html += "</div>"
    m.get_root().html.add_child(folium.Element(legend_html))

    map_out.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(map_out))
    print(f"Saved map to {map_out}")


if __name__ == "__main__":
    main()
