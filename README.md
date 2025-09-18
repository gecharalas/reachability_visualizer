# Reachability Visualizer

## Key Features

- **Interactive HTML visualization**:
	- Search bar for node ID or name
	- Click nodes to view incoming/outgoing connections and statistics
	- Highlight direct and second-degree neighbors
	- Toggle second-degree neighbor highlighting
	- Recenter and center map controls
	- Minimal, modern UI
- **Filter DOT graphs** by hops, direction, and edge status
- **Customizable**: Depth, direction, layout, and more
- **Fast**: Handles large graphs efficiently

## How to Use

### Basic usage

```bash
python3 reachability_viz.py input.dot --start NODE_ID
```

### Piping DOT input

```bash
cat input.dot | python3 reachability_viz.py --start NODE_ID
```

### Main options (defaults shown)

- `--depth 2` (default: 2 hops)
- `--direction both` (default: both directions)
- `--html reachability.html` (default: interactive HTML output)
- `--output reachability_view.dot` (default: DOT output file)
- `--splines curved` (default: curved edges)
- `--rankdir TB` (default: top-to-bottom layout)
- `--enabled-only` (show only enabled edges)
- `--render svg|png` (also render image with Graphviz)

### Example (using all defaults except start node)

```bash
python3 reachability_viz.py mygraph.dot --start 1
```

This shows 2 hops from node 1, in both directions, and exports to `reachability.html` and `reachability_view.dot`.

### Example (custom depth and output)

```bash
python3 reachability_viz.py mygraph.dot --start 1 --depth 3 --html
```

## Output Files

- `reachability_view.dot`: Filtered DOT file
- `reachability.html`: Interactive graph visualization
- `reachability.svg` / `reachability.png`: Optional rendered image

## License

MIT
- `--html`: Export interactive HTML graph (default: `reachability.html`)
