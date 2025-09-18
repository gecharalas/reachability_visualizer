# Reachability Visualizer

## What does it do?

- **Filters** a DOT graph to show only nodes within a given number of hops from a starting node (by ID or label)
- **Visualizes** the filtered graph as a DOT file, optional SVG/PNG image (via Graphviz), and a modern interactive HTML page
- **Interactive HTML** lets you search for nodes, view statistics, highlight connections, and explore the graph visually
- **Customizes** the visualization with options for direction, edge filtering, layout, and more
## Features

- **DOT graph filtering**: Show only relevant nodes and edges based on BFS from a start node
- **Interactive HTML visualization**:
	- Search bar for node ID or name
	- Click nodes to view incoming/outgoing connections and statistics
	- Highlight direct and second-degree neighbors
	- Toggle second-degree neighbor highlighting
	- Recenter and center map controls
	- Minimal, modern UI
- **Customizable options**:
	- Depth, direction, edge status filtering
	- Layout direction (vertical/horizontal)
	- Export to DOT, SVG/PNG, and HTML
- **Fast**: Handles large graphs efficiently
## Usage

Basic usage:

```bash
python3 reachability_viz.py input.dot --start NODE_ID --depth 2
```

You can also pipe DOT input via stdin:

```bash
cat input.dot | python3 reachability_viz.py --start NODE_ID --depth 2
```

### Main options

- `input.dot`: Path to DOT file (or pipe via stdin)
- `--start NODE_ID`: Start node id or label
- `--depth N`: Number of hops from start (default: 2)
- `--direction`: BFS direction (`out`, `in`, `both`)
- `--html`: Export interactive HTML graph (default: `reachability.html`)
- `--enabled-only`: Show only enabled edges
- `--render svg|png`: Also render image with Graphviz
### Example

```bash
python3 reachability_viz.py mygraph.dot --start 1 --depth 3 --html
```

## Interactive Visualization

Open the generated `reachability.html` in your browser for a rich, interactive experience:

- **Search** for nodes by ID or name
- **Click** nodes to view statistics and connections
- **Toggle** second-degree neighbor highlighting for clarity
- **Recenter** to the start node or center the map
- **Minimal UI** for distraction-free exploration
## Requirements

- Python 3
- Graphviz (optional, for image rendering)

## Output Files

- `reachability_view.dot`: Filtered DOT file
- `reachability.html`: Interactive graph visualization
- `reachability.svg` / `reachability.png`: Optional rendered image

## License

MIT
# Reachability Visualizer
```
python3 reachability_viz.py input.dot --start NODE_ID --depth 2
```

You can also pipe DOT input via stdin:

```
cat input.dot | python3 reachability_viz.py --start NODE_ID --depth 2
```

- `input.dot`: Path to DOT file (or pipe via stdin)
- `--start NODE_ID`: Start node id or label
- `--depth N`: Number of hops from start (default: 2)
- `--direction`: BFS direction (`out`, `in`, `both`)
- `--html`: Export interactive HTML graph (default: `reachability.html`)
## Usage

```bash
python3 reachability_viz.py input.dot --start NODE_ID --depth 2
```

- `input.dot`: Path to DOT file (or pipe via stdin)
- `--start NODE_ID`: Start node id or label
- `--depth N`: Number of hops from start (default: 2)
- `--direction`: BFS direction (`out`, `in`, `both`)
- `--html`: Export interactive HTML graph (default: `reachability.html`)

## Example

```bash
python3 reachability_viz.py mygraph.dot --start 1 --depth 3 --html
```

## Requirements
- Python 3
- Graphviz (optional, for image rendering)

## Output
- `reachability_view.dot`: Filtered DOT file
- `reachability.html`: Interactive graph visualization

## License
MIT
