"""
Redraw Fig 2, 4 and 5 with a Survey-of-India compliant national boundary.

Districts, edges, state lines and the choropleth still come from GADM. The SOI
national outline (full J&K, Ladakh, Gilgit-Baltistan, Aksai Chin) is drawn on
top as a thick black line. Fig 1 and 3 have no maps, so they aren't redrawn.

Boundary: compliance/india_national_boundary_soi_full.geojson, made from the
AnujTiwari India_Country_Boundary shapefile (dissolved, WGS84).
Data: ~/india-covid-network/ (node_attributes.csv, edge_list.csv, GADM L2 shp).

Run:  /Users/sanjanasingh/anaconda3/bin/python scripts/regenerate_compliance_figs.py
"""
import warnings
warnings.filterwarnings("ignore")
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from matplotlib.lines import Line2D

DATA = os.path.expanduser("~/india-covid-network")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOUNDARY = os.path.join(HERE, "compliance", "india_national_boundary_soi_full.geojson")
DEST = [
    os.path.join(HERE, "figures"),                       # repo figures
    os.path.expanduser("~/overleaf-es404/figures"),      # report figures
    DATA,                                                 # source project
]
PROJ = "EPSG:32643"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11, "axes.titlesize": 13,
    "axes.labelsize": 12, "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
})

def savefig(name):
    for d in DEST:
        os.makedirs(d, exist_ok=True)
        plt.savefig(f"{d}/{name}")
    print(f"  saved {name} -> {len(DEST)} locations")

print("Loading data...")
df = pd.read_csv(f"{DATA}/node_attributes.csv")
edges = pd.read_csv(f"{DATA}/edge_list.csv")
G = nx.Graph()
for _, row in df.iterrows():
    G.add_node(row["node_id"], state=row["state"], district=row["district"],
               betweenness_centrality=row["betweenness_centrality"] if pd.notna(row["betweenness_centrality"]) else 0,
               community=int(row["community"]) if pd.notna(row["community"]) else -1,
               total_cases=row["total_cases"] if pd.notna(row["total_cases"]) else None)
for _, row in edges.iterrows():
    G.add_edge(row["source"], row["target"])

# district geometry from GADM level 2
gdf = gpd.read_file(f"{DATA}/shapefile/gadm41_IND_2.shp").rename(columns={"NAME_1": "state", "NAME_2": "district"})
gdf["state"] = gdf["state"].str.strip()
gdf["district"] = gdf["district"].str.strip()
gdf_proj = gdf.to_crs(PROJ)
gdf_states_geo = gdf_proj.dissolve(by="state")

pos = {}
for _, row in gdf_proj.iterrows():
    nid = f"{row['state']}_{row['district']}"
    if nid in G and row["geometry"] is not None and not row["geometry"].is_empty:
        c = row["geometry"].centroid
        pos[nid] = (c.x, c.y)
nodes_with_pos = [n for n in G.nodes() if n in pos]
G_draw = G.subgraph(nodes_with_pos)

# SOI national outline, reprojected to the figure CRS
print("Loading SOI boundary...")
soi_country = gpd.read_file(BOUNDARY).to_crs(PROJ)

def draw_soi(ax, lw=2.4, color="#000000", z=12):
    """Draw the SOI national boundary on top."""
    soi_country.boundary.plot(ax=ax, linewidth=lw, color=color, zorder=z)

partition = {row["node_id"]: int(row["community"]) for _, row in df.iterrows() if pd.notna(row["community"])}
community_ids = sorted(set(partition.values()))
n_comm = len(community_ids)

# Fig 2: betweenness network map
print("Fig 2: betweenness network map")
bet_vals = np.array([G.nodes[n].get("betweenness_centrality", 0) or 0 for n in nodes_with_pos])
bet_norm = (bet_vals - bet_vals.min()) / (np.ptp(bet_vals) + 1e-10)

fig, ax = plt.subplots(figsize=(14, 16))
ax.set_facecolor("#f8f8f8"); fig.patch.set_facecolor("#f8f8f8")
gdf_states_geo.boundary.plot(ax=ax, linewidth=0.8, color="#9a9a9a", zorder=2)  # GADM state lines

jk_pos = {n: pos[n] for n in nodes_with_pos if "Jammu and Kashmir" in n}
if jk_pos:
    xs = [p[0] for p in jk_pos.values()]; ys = [p[1] for p in jk_pos.values()]
    ax.annotate("J&K and Ladakh\n(Leh and Kargil incl.)", xy=(np.mean(xs), np.mean(ys)),
                xytext=(np.mean(xs) - 200000, np.mean(ys) + 150000), fontsize=8, color="#333333",
                arrowprops=dict(arrowstyle="-", color="#666666", lw=0.8), ha="center")

nx.draw_networkx_edges(G_draw, pos, alpha=0.08, width=0.4, edge_color="#333333", ax=ax)
nx.draw_networkx_nodes(G_draw, pos, nodelist=nodes_with_pos, node_color=bet_norm,
                       cmap=cm.YlOrRd, node_size=25, ax=ax, alpha=0.9)
sm = cm.ScalarMappable(cmap=cm.YlOrRd, norm=mcolors.Normalize(vmin=bet_vals.min(), vmax=bet_vals.max()))
sm.set_array([])
plt.colorbar(sm, ax=ax, shrink=0.5, pad=0.02).set_label("Betweenness Centrality", fontsize=10)
draw_soi(ax)
ax.set_title("India District Network: Betweenness Centrality\n"
             "(666 districts, 1,784 adjacency edges; J&K and Ladakh shown in full)",
             fontsize=13, fontweight="bold")
ax.axis("off"); plt.tight_layout(); savefig("fig2_network_map.png"); plt.close()

# Fig 4: Louvain communities vs states
print("Fig 4: communities")
cmap_comm = plt.get_cmap("tab20", n_comm)
comm_colors = {c: cmap_comm(i / max(n_comm, 1)) for i, c in enumerate(community_ids)}
fig, axes = plt.subplots(1, 2, figsize=(18, 10))
fig.suptitle("Louvain Community Detection vs State Boundaries\nIndia District-Level COVID Network",
             fontsize=14, fontweight="bold")
ax = axes[0]; ax.set_facecolor("#f0f0f0")
gdf_states_geo.boundary.plot(ax=ax, linewidth=0.8, color="#9a9a9a", zorder=2)
node_colors_comm = [comm_colors[partition[n]] if n in partition else (0.5, 0.5, 0.5, 1) for n in nodes_with_pos]
nx.draw_networkx_edges(G_draw, pos, alpha=0.06, width=0.3, edge_color="#444", ax=ax)
nx.draw_networkx_nodes(G_draw, pos, nodelist=nodes_with_pos, node_color=node_colors_comm, node_size=30, ax=ax, alpha=0.9)
ax.legend(handles=[Line2D([0], [0], marker='o', color='w', markerfacecolor=comm_colors[c], markersize=8,
                          label=f"Community {c+1}") for c in community_ids],
          loc="lower left", fontsize=7, ncol=2, framealpha=0.9, title="Louvain Communities")
draw_soi(ax)
ax.set_title(f"Louvain Communities (k={n_comm})", fontsize=12); ax.axis("off")

ax2 = axes[1]; ax2.set_facecolor("#f0f0f0")
states_list = sorted(gdf["state"].unique())
state_cmap = plt.get_cmap("tab20", len(states_list))
state_color_map = {s: state_cmap(i / len(states_list)) for i, s in enumerate(states_list)}
state_vals = [state_color_map.get(G.nodes[n].get("state", ""), (0.5, 0.5, 0.5, 1)) for n in nodes_with_pos]
gdf_states_geo.boundary.plot(ax=ax2, linewidth=0.8, color="#9a9a9a", zorder=2)
nx.draw_networkx_edges(G_draw, pos, alpha=0.06, width=0.3, edge_color="#444", ax=ax2)
nx.draw_networkx_nodes(G_draw, pos, nodelist=nodes_with_pos, node_color=state_vals, node_size=30, ax=ax2, alpha=0.9)
draw_soi(ax2)
ax2.set_title("Districts Colored by State/UT", fontsize=12); ax2.axis("off")
plt.tight_layout(); savefig("fig4_communities.png"); plt.close()

# Fig 5: total cases choropleth
print("Fig 5: choropleth")
def norm(s): return str(s).lower().strip().replace("-", " ").replace(".", "")
gdf["state_norm"] = gdf["state"].apply(norm); gdf["district_norm"] = gdf["district"].apply(norm)
df["state_norm"] = df["state"].apply(norm); df["district_norm"] = df["district"].apply(norm)
gdf_merged = gdf.merge(df[["state_norm", "district_norm", "total_cases"]], on=["state_norm", "district_norm"], how="left")
gdf_plot = gdf_merged.to_crs(PROJ).copy()
gdf_plot["log_total_cases"] = np.log1p(gdf_plot["total_cases"].fillna(0))
fig, ax = plt.subplots(figsize=(12, 14)); ax.set_facecolor("#e8e8e8")
gdf_plot.plot(column="log_total_cases", cmap="Reds", linewidth=0.3, edgecolor="#888888",
              legend=True, ax=ax, legend_kwds={"label": "log(1 + Total Confirmed Cases)", "shrink": 0.5}, zorder=1)
gdf_states_geo.boundary.plot(ax=ax, linewidth=0.6, color="#9a9a9a", zorder=2)
draw_soi(ax)
ax.set_title("Total COVID-19 Cases by District (log scale)\n"
             "India, April 2020 to June 2021; J&K and Ladakh shown in full",
             fontsize=13, fontweight="bold")
ax.axis("off"); plt.tight_layout(); savefig("fig5_cases_choropleth.png"); plt.close()

print("\nDone, redrew Fig 2, 4, 5.")
