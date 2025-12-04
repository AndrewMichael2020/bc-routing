#!/usr/bin/env python3
import osmnx as ox

G = ox.load_graphml("data/master/merged.graphml")

u = 10199121387  # Surrey node
v = 13053107295  # Hope node

path = ox.shortest_path(G, u, v, weight="travel_time")

print("Nodes in path:", len(path))

fig, ax = ox.plot_graph_route(
    G,
    path,
    node_size=0,
    bgcolor="white",
    edge_color="#cccccc",
    edge_linewidth=0.5,
    route_color="red",
    route_linewidth=2,
)