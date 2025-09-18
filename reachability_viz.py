#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
import shutil
import subprocess
import sys
import json
from collections import defaultdict

NODE_RE = re.compile(r'(\d+)\s*\[label="([^"]*)"\]')
EDGE_RE = re.compile(r'(\d+)\s*->\s*(\d+)\s*\[label="([^"]*)"\]')

def parse_source_text(source_text):
    nodes = {}
    original_nodes = {}
    edges = []
    for m in NODE_RE.finditer(source_text):
        nid = int(m.group(1))
        label = m.group(2).strip()
        if nid not in nodes or not nodes[nid]:
            nodes[nid] = label
            original_nodes[nid] = label
    for m in EDGE_RE.finditer(source_text):
        src = int(m.group(1)); dst = int(m.group(2))
        raw = m.group(3).strip()
        status = extract_status(raw)
        edges.append({"src": src, "dst": dst, "raw_label": raw, "status": status})
    return nodes, edges, original_nodes

def extract_status(raw_label):
    if not raw_label:
        return 'E'
    parts = [p.strip() for p in raw_label.split('|')]
    first = (parts[0].upper() if parts else '')
    if first.startswith('S'): return 'S'
    if first.startswith('D'): return 'D'
    if first.startswith('E'): return 'E'
    return 'E'

# --- New utility to merge bidirectional edges ---
def merge_bidirectional_edges(edges):
    merged = []
    seen = {}
    for e in edges:
        s, d = e["src"], e["dst"]
        key = tuple(sorted([s, d]))
        if key in seen:
            # Already saw opposite edge, merge into one
            other = seen[key]
            other["bidirectional"] = True
        else:
            entry = e.copy()
            entry["bidirectional"] = False
            merged.append(entry)
            seen[key] = entry
    return merged

def build_adjacency(edges):
    out_adj = defaultdict(set)
    in_adj = defaultdict(set)
    for e in edges:
        out_adj[e["src"]].add(e["dst"])
        in_adj[e["dst"]].add(e["src"])
    return out_adj, in_adj

def bfs_levels(start, depth, out_adj, in_adj, direction):
    if depth < 0: depth = 0
    visited = {start}
    levels = [set([start])]
    frontier = set([start])

    def neighbors(u):
        if direction == 'out':  return out_adj.get(u, set())
        if direction == 'in':   return in_adj.get(u, set())
        return out_adj.get(u, set()) | in_adj.get(u, set())

    for _ in range(depth):
        nxt = set()
        for u in frontier:
            for v in neighbors(u):
                if v not in visited:
                    visited.add(v)
                    nxt.add(v)
        if not nxt: break
        levels.append(nxt)
        frontier = nxt
    return levels, visited

def escape_label(text):
    if text is None: return ""
    return text.replace("\\", "\\\\").replace("\"", "\\\"")

def ports_for_rankdir(rankdir):
    if rankdir in ('LR', 'RL'):
        return ('e', 'w') if rankdir=='LR' else ('w','e')
    else:
        return ('s','n') if rankdir=='TB' else ('n','s')

def generate_dot(nodes, edges, included_nodes, levels, start,
                 rankdir='TB', edge_labels='status',
                 splines='curved', no_overlap=True, concentrate=False,
                 nodesep=0.6, ranksep=1.0, use_ports=False,
                 level_edges_only=False, deemphasize_cross=True):
    level_index = {}
    for i, grp in enumerate(levels):
        for n in grp: level_index[n] = i

    lines = []
    lines.append('digraph G {')
    lines.append(f'  rankdir={rankdir};')

    graph_attrs = [ 'fontsize=10', 'labelloc="t"', 'fontname="Segoe UI"' ]
    if splines:
        graph_attrs.append(f'splines={splines}')
    if no_overlap:
        graph_attrs.append('overlap=false')
        graph_attrs.append('sep="+15,15"')
    if concentrate:
        graph_attrs.append('concentrate=true')
    graph_attrs.append(f'nodesep={nodesep}')
    graph_attrs.append(f'ranksep="{ranksep} equally"')

    lines.append(f'  graph [{", ".join(graph_attrs)}];')
    lines.append('  node [shape=circle, style=filled, width=0.5, fixedsize=true, fillcolor="#f0f4ff", fontname="Segoe UI", fontsize=9];')
    lines.append('  edge [fontname="Segoe UI", fontsize=8, arrowsize=0.7];')
    lines.append('')

    for nid in sorted(included_nodes):
        name = nodes.get(nid, '')
        display = f'{nid}\\n{name}' if name else f'{nid}'
        fill = '#fff3cd' if nid == start else '#f0f4ff'
        lines.append(f'  {nid} [label="{escape_label(display)}", fillcolor="{fill}"];')
    lines.append('')

    for lvl, group in enumerate(levels):
        if not group: continue
        same_rank_nodes = " ".join(str(n) for n in sorted(group))
        lines.append(f'  {{ rank=same; /* level {lvl} */ {same_rank_nodes}; }}')
    lines.append('')

    tailport, headport = ports_for_rankdir(rankdir) if use_ports else (None, None)

    for e in edges:
        s, d = e["src"], e["dst"]
        if s not in included_nodes or d not in included_nodes:
            continue

        s_lvl = level_index.get(s, None)
        d_lvl = level_index.get(d, None)
        delta = None if (s_lvl is None or d_lvl is None) else (d_lvl - s_lvl)

        if level_edges_only and (delta is None or abs(delta) != 1):
            continue

        status = e["status"]
        if status == 'E':
            base_color = '#2e7d32'
            base_style = 'solid'
            base_width = 1.8
        elif status == 'S':
            base_color = '#b71c1c'
            base_style = 'dashed'
            base_width = 1.2
        else:  # status == 'D'
            base_color = '#666666'
            base_style = 'dotted'
            base_width = 1.0

        attrs = []
        if deemphasize_cross and delta is not None and abs(delta) != 1:
            attrs.append('constraint=false')
            attrs.append('style=dotted')
            attrs.append('color="#999999"')
            attrs.append('penwidth=0.9')
            if delta is not None and abs(delta) > 1:
                attrs.append(f'minlen={abs(delta)}')
        else:
            attrs.append(f'color="{base_color}"')
            attrs.append(f'style="{base_style}"')
            attrs.append(f'penwidth="{base_width}"')

        if edge_labels == 'full':
            attrs.append(f'label="{escape_label(e["raw_label"])}"')
        elif edge_labels == 'status':
            # Skip adding status labels since we're already painting edges with different colors/styles
            pass

        if tailport: attrs.append(f'tailport={tailport}')
        if headport: attrs.append(f'headport={headport}')

        lines.append(f'  {s} -> {d} [{", ".join(attrs)}];')

    lines.append('}')
    return "\n".join(lines)

def detect_graphviz():
    return shutil.which('dot')

def render_with_graphviz(dot_path, out_format='svg', output_path=None, layout='dot'):
    dot_bin = detect_graphviz()
    if not dot_bin:
        print("Graphviz 'dot' not found in PATH. Skipping rendering.", file=sys.stderr)
        return None
    if output_path is None:
        base, _ = os.path.splitext(dot_path)
        output_path = f"{base}.{out_format}"
    cmd = [dot_bin, f'-K{layout}', f'-T{out_format}', dot_path, '-o', output_path]
    try:
        subprocess.run(cmd, check=True)
        return output_path
    except subprocess.CalledProcessError as exc:
        print(f"Graphviz rendering failed: {exc}", file=sys.stderr)
        return None

def export_html(nodes, edges, included_nodes, output_html="reachability.html", start_node=None, original_nodes=None, levels=None, node_levels=None):
    vis_nodes = []

    # Calculate dynamic spacing based on average and max label length
    avg_label_len = sum(len(nodes.get(nid, str(nid))) for nid in included_nodes) / max(1, len(included_nodes))
    max_label_len = max(len(nodes.get(nid, str(nid))) for nid in included_nodes)
    # Add extra spacing for long labels
    node_spacing = 100 + int(avg_label_len * 6) + int(max_label_len * 2)
    level_separation = 60 + int(avg_label_len * 3) + int(max_label_len * 1)

    # Split wide levels into sub-levels of max 30 nodes and assign levels to nodes
    def split_levels(levels, max_per_level=30):
        new_levels = []
        node_levels = {}
        level_idx = 0
        for group in levels:
            group = list(group)
            for i in range(0, len(group), max_per_level):
                sub_group = set(group[i:i+max_per_level])
                new_levels.append(sub_group)
                for nid in sub_group:
                    node_levels[nid] = level_idx
                level_idx += 1
        return new_levels, node_levels
    levels, node_levels = split_levels(levels, max_per_level=30)

    for nid in included_nodes:
        label = nodes.get(nid, str(nid))
        base_size = 25 if nid == start_node else 18
        size = base_size + min(64, int(len(label) * 3.2))
        node_data = {
            "id": nid,
            "label": label,
            "color": {
                "background": "#34d399" if nid == start_node else "#f0f4ff",  # Green for start node
                "border": "#059669" if nid == start_node else "#2196F3",
                "highlight": {
                    "background": "#6ee7b7" if nid == start_node else "#ffff99",
                    "border": "#059669" if nid == start_node else "#ffcc00"
                }
            },
            "size": size,
            "font": {"size": 14 if nid == start_node else 12, "color": "#333"}
        }
        node_data['level'] = node_levels.get(nid, 0)
        vis_nodes.append(node_data)
    
    vis_edges = []
    edge_id = 0
    for e in edges:
        if e["src"] in included_nodes and e["dst"] in included_nodes:
            # Configure arrows based on whether edge is bidirectional
            arrows_config = "to,from" if e.get("bidirectional", False) else "to"
            
            # Color and style based on status
            if e["status"] == "E":
                edge_color = "#81c784"
                edge_width = 0.6
                edge_dashes = False
            elif e["status"] == "S":
                edge_color = "#e57373"
                edge_width = 0.5
                edge_dashes = [5, 5]
            else:  # status == "D"
                edge_color = "#999999"
                edge_width = 0.4
                edge_dashes = [2, 3]
            
            edge_data = {
                "id": edge_id,
                "from": e["src"], 
                "to": e["dst"],
                "status": e["status"],  # Store original status
                "arrows": arrows_config,
                "color": {
                    "color": edge_color,
                    "highlight": "#ffcc00",
                    "hover": "#ffcc00"
                },
                "width": edge_width,
                "dashes": edge_dashes
            }
            vis_edges.append(edge_data)
            edge_id += 1

    # Assign level property to vis_nodes for hierarchical layout
    for node in vis_nodes:
        node['level'] = node_levels.get(node['id'], 0)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <title>Reachability Graph</title>
      <script type=\"text/javascript\" src=\"https://unpkg.com/vis-network/standalone/umd/vis-network.min.js\"></script>
      <style> 
        body {{
          margin: 0;
          padding: 0;
          font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        #mynetwork {{ width: 100%; height: 100vh; }} 
        #info {{ 
          position: absolute; 
          top: 16px; 
          left: 16px; 
          width: 600px;
          max-height: 75vh;
          background: rgba(255,255,255,0.95); 
          padding: 20px; 
          border-radius: 16px; 
          border: none;
          box-shadow: 0 8px 32px rgba(0,0,0,0.08), 0 2px 16px rgba(0,0,0,0.04);
          overflow-y: auto;
          overflow-x: hidden;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: 13px;
          line-height: 1.5;
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          z-index: 1000;
          scrollbar-width: thin;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          display: none;
        }}
        #info.show {{
          display: block;
          animation: fadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        @keyframes fadeIn {{
          from {{
            opacity: 0;
            transform: translateY(-10px);
          }}
          to {{
            opacity: 1;
            transform: translateY(0);
          }}
        }}
        #info:hover {{
          box-shadow: 0 12px 48px rgba(0,0,0,0.12), 0 4px 24px rgba(0,0,0,0.06);
        }}
        #info::-webkit-scrollbar {{
          width: 6px;
        }}
        #info::-webkit-scrollbar-track {{
          background: rgba(248,250,252,0.6);
          border-radius: 10px;
        }}
        #info::-webkit-scrollbar-thumb {{
          background: linear-gradient(180deg, #cbd5e1, #94a3b8);
          border-radius: 10px;
        }}
        #info::-webkit-scrollbar-thumb:hover {{
          background: linear-gradient(180deg, #94a3b8, #64748b);
        }}
        .connection-list {{
          display: flex;
          flex-direction: column;
          gap: 4px;
          margin-top: 5px;
        }}
        .connection-item {{
          background: rgba(248,250,252,0.8);
          padding: 8px 12px;
          border-radius: 10px;
          border: none;
          font-size: 11px;
          font-weight: 400;
          word-wrap: break-word;
          overflow-wrap: break-word;
          cursor: pointer;
          transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
          line-height: 1.4;
          color: #475569;
          box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .connection-item:hover {{
          background: rgba(59,130,246,0.08);
          color: #1e40af;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(59,130,246,0.15);
        }}
        .connection-item:active {{
          transform: translateY(0);
          box-shadow: 0 2px 8px rgba(59,130,246,0.2);
        }}
        #search-container {{
          position: absolute;
          top: 16px;
          right: 16px;
          z-index: 1000;
          width: 400px;
        }}
        #search-input {{
          width: 100%;
          padding: 16px 20px;
          border: 2px solid rgba(180,180,180,0.7); /* grey border to match notification */
          border-radius: 16px;
          font-size: 15px;
          font-weight: 500;
          box-sizing: border-box;
          background: rgba(255,255,255,0.98);
          color: #222;
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          box-shadow: 0 8px 32px rgba(0,0,0,0.10), 0 2px 16px rgba(0,0,0,0.04);
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        #search-input::placeholder {{
          color: #888;
          font-weight: 500;
        }}
        #search-input:focus {{
          outline: none;
          border: 2px solid #888;
          background: #fff;
        }}
        #search-results {{
          max-height: 280px;
          overflow-y: auto;
          margin-top: 6px;
          background: rgba(255,255,255,0.95);
          border: none;
          border-radius: 16px;
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          box-shadow: 0 8px 32px rgba(0,0,0,0.08), 0 2px 16px rgba(0,0,0,0.04);
          display: none;
          scrollbar-width: thin;
        }}
        #search-results.show {{
          display: block;
          animation: slideDown 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        @keyframes slideDown {{
          from {{
            opacity: 0;
            transform: translateY(-8px);
          }}
          to {{
            opacity: 1;
            transform: translateY(0);
          }}
        }}
        #search-results::-webkit-scrollbar {{
          width: 4px;
        }}
        #search-results::-webkit-scrollbar-track {{
          background: transparent;
        }}
        #search-results::-webkit-scrollbar-thumb {{
          background: rgba(148,163,184,0.4);
          border-radius: 10px;
        }}
        .search-result {{
          padding: 12px 18px;
          cursor: pointer;
          font-size: 13px;
          font-weight: 400;
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
          border-bottom: 1px solid rgba(226,232,240,0.3);
          color: #334155;
        }}
        .search-result:hover {{
          background: rgba(59,130,246,0.05);
          color: #1e40af;
          /* Remove horizontal movement */
        }}
        .search-result:active {{
          background: rgba(59,130,246,0.1);
        }}
        .search-result:last-child {{
          border-bottom: none;
        }}
        .no-results {{
          padding: 16px 18px;
          color: #64748b;
          font-style: italic;
          font-size: 13px;
          text-align: center;
        }}
        .show-more-results:hover {{
          background: rgba(59,130,246,0.08) !important;
          color: #1d4ed8 !important;
          /* Remove any navigation bar styling */
        }}
        #instruction-overlay {{
          position: absolute;
          bottom: 20px;
          left: 20px;
          background: rgba(0,0,0,0.7);
          color: rgba(255,255,255,0.9);
          padding: 8px 16px;
          border-radius: 20px;
          font-size: 13px;
          font-weight: 400;
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          z-index: 500;
          transition: opacity 0.3s ease;
          cursor: pointer;
        }}
        #instruction-overlay.fade {{
          opacity: 0.6;
        }}
      </style>
    </head>
    <body>
      <div id=\"info\"></div>
      <div id=\"search-container\">
        <input type=\"text\" id=\"search-input\" placeholder=\"Search positions by ID or name...\" />
        <div id=\"search-results\"></div>
      </div>
      <div id=\"instruction-overlay\">Hover over nodes to see connections. Click for statistics.<br>Press <b>U</b> to freeze/unfreeze map.</div>
      <div id=\"mynetwork\"></div>
      <script>
        var nodes = new vis.DataSet({json.dumps(vis_nodes)});
        var edges = new vis.DataSet({json.dumps(vis_edges)});
        var originalNames = {json.dumps(original_nodes or {{}})};
        var container = document.getElementById('mynetwork');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
          layout: {{
            hierarchical: {{
              enabled: true,
              direction: 'UD',
              nodeSpacing: {node_spacing},
              levelSeparation: {level_separation},
              sortMethod: 'hubsize'
            }}
          }},
          physics: {{ enabled: false }},
          interaction: {{ 
            hover: true,
            selectConnectedEdges: true,
            hoverConnectedEdges: true
          }},
          edges: {{
            smooth: {{ type: 'curvedCW', roundness: 0.2 }},
            chosen: true
          }},
          nodes: {{
            chosen: true
          }}
        }};
        
        var network = new vis.Network(container, data, options);
        
        // Focus on the start node when the network is ready
        network.once('afterDrawing', function() {{
          if ({start_node}) {{
            network.focus({start_node}, {{
              scale: 1.0,
              offset: {{x: 0, y: 0}},
              animation: {{
                duration: 1000,
                easingFunction: 'easeInOutQuad'
              }}
            }});
            
            // Also select the start node to highlight it
            network.selectNodes([{start_node}]);
            highlightNodeAndEdges({start_node}); // Automatically open statistics window
          }}
        }});
        
        // Store original properties for reset
        var originalNodeColors = {{}};
        var originalEdgeProperties = {{}};
        
        nodes.forEach(function(node) {{
          originalNodeColors[node.id] = {{
            background: node.color.background,
            border: node.color.border
          }};
        }});
        
        edges.forEach(function(edge) {{
          originalEdgeProperties[edge.id] = {{
            color: edge.color,
            width: edge.width
          }};
        }});
        
        // Handle scrolling in the info panel properly
        var infoPanel = document.getElementById('info');
        var isOverInfoPanel = false;
        
        infoPanel.addEventListener('mouseenter', function(e) {{
          isOverInfoPanel = true;
          // Disable network interactions when over info panel
          network.setOptions({{
            interaction: {{
              dragView: false,
              zoomView: false,
              hover: false,
              selectConnectedEdges: true,
              hoverConnectedEdges: true
            }}
          }});
        }});
        
        infoPanel.addEventListener('mouseleave', function(e) {{
          isOverInfoPanel = false;
          // Always fully re-enable all network interactions when leaving info panel
          network.setOptions({{
            interaction: {{
              dragView: true,
              zoomView: true,
              hover: true,
              selectConnectedEdges: true,
              hoverConnectedEdges: true,
              multiselect: true,
              navigationButtons: false
            }}
          }});
        }});
        
        // Handle wheel events on the entire document
        document.addEventListener('wheel', function(e) {{
          if (isOverInfoPanel) {{
            // Allow scrolling within the info panel, prevent it from reaching the network
            var target = e.target;
            while (target && target !== document) {{
              if (target === infoPanel) {{
                // We're scrolling inside the info panel - allow it but stop propagation
                e.stopPropagation();
                return;
              }}
              target = target.parentNode;
            }}
            // If we get here, prevent the scroll from affecting the network
            e.preventDefault();
            e.stopPropagation();
          }}
        }}, {{ passive: false }});
        
        // Track if a node is explicitly selected (clicked)
        var selectedNodeId = null;
        
        // Only update statistics and highlight on click/select
        network.on("selectNode", function(params) {{
          if (params.nodes.length > 0) {{
            // Reset previous highlighting before applying new one
            resetHighlight();
            selectedNodeId = params.nodes[0];
            highlightNodeAndEdges(params.nodes[0]);
          }}
        }});
        
        // Reset highlighting when deselecting or clicking empty space
        network.on("deselectNode", function(params) {{
          selectedNodeId = null;
          resetHighlight();
          // Re-enable hover events so highlighting works immediately
          network.setOptions({{
            interaction: {{
              hover: true,
              hoverConnectedEdges: true
            }}
          }});
        }});
        
        // Also reset when clicking on empty space
        network.on("click", function(params) {{
          if (params.nodes.length === 0) {{
            selectedNodeId = null;
            network.unselectAll();
            resetHighlight();
            // Re-enable hover events so highlighting works immediately
            network.setOptions({{
              interaction: {{
                hover: true,
                hoverConnectedEdges: true
              }}
            }});
          }}
        }});
        
        // Search functionality
        var searchInput = document.getElementById('search-input');
        var searchResults = document.getElementById('search-results');
        
        function performSearch(query, showAll) {{
          if (!query.trim()) {{
            searchResults.innerHTML = '';
            searchResults.classList.remove('show');
            return;
          }}
          
          var results = [];
          var lowerQuery = query.toLowerCase();
          
          // Search through all nodes
          nodes.forEach(function(node) {{
            var nodeId = node.id.toString();
            var originalName = originalNames[node.id] || '';
            var displayName = node.label.split('\\\\n')[1] || node.label.split('\\\\n')[0] || '';
            
            // Check if query matches ID or any part of the name
            if (nodeId.includes(lowerQuery) || 
                originalName.toLowerCase().includes(lowerQuery) ||
                displayName.toLowerCase().includes(lowerQuery)) {{
              results.push({{
                id: node.id,
                name: originalName,
                displayName: displayName
              }});
            }}
          }});
          
          // Display results
          if (results.length === 0) {{
            searchResults.innerHTML = '<div class="no-results">No positions found</div>';
            searchResults.classList.add('show');
          }} else {{
            var html = '';
            var displayCount = showAll ? results.length : Math.min(10, results.length);
            
            results.slice(0, displayCount).forEach(function(result) {{
              html += '<div class="search-result" data-node-id="' + result.id + '">' +
                     result.id + ' - <strong>' + (result.name || result.displayName) + '</strong></div>';
            }});
            
            if (!showAll && results.length > 10) {{
              html += '<div class="show-more-results" data-all-results="true" style="padding: 12px 18px; cursor: pointer; color: #3b82f6; font-weight: 500; text-align: center; border-top: 1px solid rgba(226,232,240,0.5); background: rgba(59,130,246,0.02); transition: background 0.2s;">Show all ' + results.length + ' results</div>';
            }}
            
            searchResults.innerHTML = html;
            searchResults.classList.add('show');
          }}
        }}
        
        function markSearchResults(query) {{
          var lowerQuery = query.toLowerCase();
          var nodeUpdates = [];
          nodes.forEach(function(node) {{
            var label = node.label.toLowerCase();
            if (label.includes(lowerQuery) || label.startsWith(lowerQuery)) {{
              nodeUpdates.push({{
                id: node.id,
                color: {{
                  background: '#fde68a',
                  border: '#f59e42',
                  highlight: {{ background: '#fff8dc', border: '#f59e42' }}
                }},
                font: {{ color: node.font.color, size: node.font.size }}
              }});
            }} else {{
              nodeUpdates.push({{
                id: node.id,
                color: originalNodeColors[node.id],
                font: {{ color: node.font.color, size: node.font.size }}
              }});
            }}
          }});
          nodes.update(nodeUpdates);
        }}

        searchInput.addEventListener('input', function(e) {{
          performSearch(e.target.value);
          if (e.target.value.trim()) {{
            markSearchResults(e.target.value);
          }} else {{
            resetHighlight();
          }}
        }});
        
        function selectAndFocusNode(nodeId) {{
          // Reset previous highlighting before applying new one
          resetHighlight();
          // Always fully re-enable all network interactions after traveling to a node
          network.setOptions({{
            interaction: {{
              dragView: true,
              zoomView: true,
              hover: true,
              selectConnectedEdges: true,
              hoverConnectedEdges: true,
              multiselect: true,
              navigationButtons: false
            }}
          }});
          // Focus on the node
          network.focus(nodeId, {{
            scale: 1.2,
            animation: {{
              duration: 800,
              easingFunction: 'easeInOutQuad'
            }}
          }});
          // Select the node
          network.selectNodes([nodeId]);
          selectedNodeId = nodeId;
          highlightNodeAndEdges(nodeId);
          // Clear search
          searchInput.value = '';
          searchResults.innerHTML = '';
          searchResults.classList.remove('show');
        }}
        
        // Search input event listeners
        searchInput.addEventListener('input', function(e) {{
          performSearch(e.target.value);
        }});
        
        searchInput.addEventListener('keydown', function(e) {{
          if (e.key === 'Enter') {{
            var firstResult = searchResults.querySelector('.search-result');
            if (firstResult) {{
              var nodeId = parseInt(firstResult.getAttribute('data-node-id'));
              selectAndFocusNode(nodeId);
            }}
          }} else if (e.key === 'Escape') {{
            searchInput.value = '';
            searchResults.innerHTML = '';
            searchResults.classList.remove('show');
          }}
        }});
        
        // Click on search results - use event delegation for better reliability
        searchResults.addEventListener('click', function(e) {{
          var target = e.target;
          
          // Check if clicked on "Show more results"
          if (target.classList && target.classList.contains('show-more-results')) {{
            var currentQuery = searchInput.value;
            performSearch(currentQuery, true); // Pass true to show all results
            // Do NOT hide or change instruction overlay visibility
            return;
          }}
          
          // Find the search-result element (might be clicked on child element)
          while (target && target !== searchResults) {{
            if (target.classList && target.classList.contains('search-result')) {{
              var nodeId = parseInt(target.getAttribute('data-node-id'));
              if (!isNaN(nodeId)) {{
                selectAndFocusNode(nodeId);
                return;
              }}
            }}
            target = target.parentNode;
          }}
        }});
        
        function highlightNodeAndEdges(nodeId) {{
          var connectedNodes = network.getConnectedNodes(nodeId);
          var connectedEdges = network.getConnectedEdges(nodeId);
          // Highlight selected node (same size as others)
          var nodeUpdates = [{{
            id: nodeId,
            color: {{
              background: '#fde68a',
              border: '#f59e42',
              highlight: {{ background: '#fff8dc', border: '#f59e42' }}
            }},
            font: {{ color: '#222', size: 13 }}
          }}];
          // Highlight directly connected nodes
          connectedNodes.forEach(function(nid) {{
            nodeUpdates.push({{
              id: nid,
              color: {{
                background: '#fffbe6',
                border: '#ffd700',
                highlight: {{ background: '#fffbe6', border: '#ffd700' }}
              }},
              font: {{ color: '#333', size: 13 }}
            }});
          }});
          // Highlight second-degree neighbors (brothers) with a noticeable color
          var secondDegree = new Set();
          connectedNodes.forEach(function(nid) {{
            network.getConnectedNodes(nid).forEach(function(nid2) {{
              if (nid2 !== nodeId && !connectedNodes.includes(nid2)) {{
                secondDegree.add(nid2);
              }}
            }});
          }});
          secondDegree.forEach(function(nid) {{
            nodeUpdates.push({{
              id: nid,
              color: {{
                background: '#60a5fa', // Vibrant blue
                border: '#2563eb',
                highlight: {{ background: '#60a5fa', border: '#2563eb' }}
              }},
              font: {{ color: '#222', size: 13 }}
            }});
          }});
          nodes.update(nodeUpdates);
          // Get current node name - use original unabbreviated name
          var currentNodeName = originalNames[nodeId] || 'unnamed';
          
          // Analyze connected edges by type and direction
          var edgeAnalysis = {{ inEnabled: 0, inSuspended: 0, inDisabled: 0, outEnabled: 0, outSuspended: 0, outDisabled: 0,
                               inEnabledNodes: [], inSuspendedNodes: [], inDisabledNodes: [], outEnabledNodes: [], outSuspendedNodes: [], outDisabledNodes: [] }};
          
          connectedEdges.forEach(function(edgeId) {{
            var edgeData = edges.get(edgeId);
            var isOutgoing = (edgeData.from == nodeId);
            var status = edgeData.status; // Use original status
            var targetNodeId = isOutgoing ? edgeData.to : edgeData.from;
            var targetNodeName = originalNames[targetNodeId] || 'unnamed';
            var targetInfo = {{
              nodeId: targetNodeId,
              displayText: targetNodeId + ' (<b>' + targetNodeName + '</b>)'
            }};
            // If edge is bidirectional, count as both incoming and outgoing
            if (edgeData.arrows && edgeData.arrows.includes('from') && edgeData.arrows.includes('to')) {{
              // Outgoing
              if (status === 'E') {{
                edgeAnalysis.outEnabled++;
                edgeAnalysis.outEnabledNodes.push(targetInfo);
              }} else if (status === 'S') {{
                edgeAnalysis.outSuspended++;
                edgeAnalysis.outSuspendedNodes.push(targetInfo);
              }} else {{
                edgeAnalysis.outDisabled++;
                edgeAnalysis.outDisabledNodes.push(targetInfo);
              }}
              // Incoming
              if (status === 'E') {{
                edgeAnalysis.inEnabled++;
                edgeAnalysis.inEnabledNodes.push(targetInfo);
              }} else if (status === 'S') {{
                edgeAnalysis.inSuspended++;
                edgeAnalysis.inSuspendedNodes.push(targetInfo);
              }} else {{
                edgeAnalysis.inDisabled++;
                edgeAnalysis.inDisabledNodes.push(targetInfo);
              }}
            }} else {{
              // Normal direction
              if (isOutgoing) {{
                if (status === 'E') {{
                  edgeAnalysis.outEnabled++;
                  edgeAnalysis.outEnabledNodes.push(targetInfo);
                }} else if (status === 'S') {{
                  edgeAnalysis.outSuspended++;
                  edgeAnalysis.outSuspendedNodes.push(targetInfo);
                }} else {{
                  edgeAnalysis.outDisabled++;
                  edgeAnalysis.outDisabledNodes.push(targetInfo);
                }}
              }} else {{
                if (status === 'E') {{
                  edgeAnalysis.inEnabled++;
                  edgeAnalysis.inEnabledNodes.push(targetInfo);
                }} else if (status === 'S') {{
                  edgeAnalysis.inSuspended++;
                  edgeAnalysis.inSuspendedNodes.push(targetInfo);
                }} else {{
                  edgeAnalysis.inDisabled++;
                  edgeAnalysis.inDisabledNodes.push(targetInfo);
                }}
              }}
            }}
          }});
          
          // Build info display with better layout for many connections
          var totalConnections = edgeAnalysis.outEnabled + edgeAnalysis.outSuspended + edgeAnalysis.outDisabled +
                                  edgeAnalysis.inEnabled + edgeAnalysis.inSuspended + edgeAnalysis.inDisabled;
          
          // Helper function to create beautiful connection lists
          function createConnectionList(connections, color) {{
            if (connections.length === 0) return '';
            var listHtml = '<div class="connection-list">';
            connections.forEach(function(connection) {{
              listHtml += '<div class="connection-item" data-target-node="' + connection.nodeId + '" style="border-left: 3px solid ' + color + ';">' + connection.displayText + '</div>';
            }});
            listHtml += '</div>';
            return listHtml;
          }}
          
          var infoHtml = '<div style="margin-bottom: 10px;"><strong>Selected:</strong> ' + nodeId + ' (<b>' + (currentNodeName || 'unnamed') + '</b>)<br>';
          infoHtml += '<strong>Total Connections:</strong> ' + totalConnections + '</div>';
          
          // Two-column layout for connections
          var hasIncoming = (edgeAnalysis.inEnabled > 0 || edgeAnalysis.inSuspended > 0 || edgeAnalysis.inDisabled > 0);
          var hasOutgoing = (edgeAnalysis.outEnabled > 0 || edgeAnalysis.outSuspended > 0 || edgeAnalysis.outDisabled > 0);
          
          if (hasIncoming || hasOutgoing) {{
            infoHtml += '<div style="display: flex; gap: 15px; margin-bottom: 15px;">';
            
            // Incoming section (left column)
            infoHtml += '<div style="flex: 1; min-width: 0;">';
            if (hasIncoming) {{
              var inTotal = edgeAnalysis.inEnabled + edgeAnalysis.inSuspended + edgeAnalysis.inDisabled;
              infoHtml += '<div style="margin-bottom: 10px; font-size: 15px; font-weight: bold;"><b>Incoming (' + inTotal + ') &lt;--</b></div>';
              
              if (edgeAnalysis.inEnabled > 0) {{
                infoHtml += '<div style="margin: 8px 0 5px 0;"><span style="color: #81c784; font-weight: bold;">[E]</span> <strong>Enabled (' + edgeAnalysis.inEnabled + ')</strong></div>';
                infoHtml += createConnectionList(edgeAnalysis.inEnabledNodes, '#81c784');
              }}
              
              if (edgeAnalysis.inSuspended > 0) {{
                infoHtml += '<div style="margin: 8px 0 5px 0;"><span style="color: #e57373; font-weight: bold;">[S]</span> <strong>Suspended (' + edgeAnalysis.inSuspended + ')</strong></div>';
                infoHtml += createConnectionList(edgeAnalysis.inSuspendedNodes, '#e57373');
              }}
              
              if (edgeAnalysis.inDisabled > 0) {{
                infoHtml += '<div style="margin: 8px 0 5px 0;"><span style="color: #999999; font-weight: bold;">[D]</span> <strong>Disabled (' + edgeAnalysis.inDisabled + ')</strong></div>';
                infoHtml += createConnectionList(edgeAnalysis.inDisabledNodes, '#999999');
              }}
            }} else {{
              infoHtml += '<div style="margin-bottom: 10px; color: #888; font-size: 15px; font-weight: bold;"><b>Incoming (0) &lt;--</b></div>';
              infoHtml += '<div style="color: #888; font-style: italic; font-size: 11px;">No incoming connections</div>';
            }}
            infoHtml += '</div>';
            
            // Outgoing section (right column)
            infoHtml += '<div style="flex: 1; min-width: 0;">';
            if (hasOutgoing) {{
              var outTotal = edgeAnalysis.outEnabled + edgeAnalysis.outSuspended + edgeAnalysis.outDisabled;
              infoHtml += '<div style="margin-bottom: 10px; font-size: 15px; font-weight: bold;"><b>Outgoing (' + outTotal + ') --&gt;</b></div>';
              
              if (edgeAnalysis.outEnabled > 0) {{
                infoHtml += '<div style="margin: 8px 0 5px 0;"><span style="color: #81c784; font-weight: bold;">[E]</span> <strong>Enabled (' + edgeAnalysis.outEnabled + ')</strong></div>';
                infoHtml += createConnectionList(edgeAnalysis.outEnabledNodes, '#81c784');
              }}
              
              if (edgeAnalysis.outSuspended > 0) {{
                infoHtml += '<div style="margin: 8px 0 5px 0;"><span style="color: #e57373; font-weight: bold;">[S]</span> <strong>Suspended (' + edgeAnalysis.outSuspended + ')</strong></div>';
                infoHtml += createConnectionList(edgeAnalysis.outSuspendedNodes, '#e57373');
              }}
              
              if (edgeAnalysis.outDisabled > 0) {{
                infoHtml += '<div style="margin: 8px 0 5px 0;"><span style="color: #999999; font-weight: bold;">[D]</span> <strong>Disabled (' + edgeAnalysis.outDisabled + ')</strong></div>';
                infoHtml += createConnectionList(edgeAnalysis.outDisabledNodes, '#999999');
              }}
            }} else {{
              infoHtml += '<div style="margin-bottom: 10px; color: #888; font-size: 15px; font-weight: bold;"><b>Outgoing (0) --&gt;</b></div>';
              infoHtml += '<div style="color: #888; font-style: italic; font-size: 11px;">No outgoing connections</div>';
            }}
            infoHtml += '</div>';
            
            infoHtml += '</div>';
          }}
          
          var infoElement = document.getElementById('info');
          infoElement.innerHTML = infoHtml;
          infoElement.classList.add('show');
        }}
        
        // Add event delegation for clicking on connection items in statistics
        document.getElementById('info').addEventListener('click', function(e) {{
          var target = e.target;
          
          // Find the connection-item element (might be clicked on child element like <b>)
          while (target && target !== document.getElementById('info')) {{
            if (target.classList && target.classList.contains('connection-item')) {{
              var targetNodeId = parseInt(target.getAttribute('data-target-node'));
              if (!isNaN(targetNodeId)) {{
                resetHighlight();
                selectAndFocusNode(targetNodeId);
                // After focusing, ensure hover events are enabled and highlight works
                network.setOptions({{
                  interaction: {{
                    hover: true,
                    hoverConnectedEdges: true
                  }}
                }});
                return;
              }}
            }}
            target = target.parentNode;
          }}
        }});
        
        function resetHighlight() {{
          // Reset all nodes to original colors
          var nodeUpdates = [];
          Object.keys(originalNodeColors).forEach(function(nodeId) {{
            nodeUpdates.push({{
              id: parseInt(nodeId),
              color: originalNodeColors[nodeId]
            }});
          }});
          nodes.update(nodeUpdates);
          
          // Reset all edges to original properties
          var edgeUpdates = [];
          Object.keys(originalEdgeProperties).forEach(function(edgeId) {{
            var original = originalEdgeProperties[edgeId];
            edgeUpdates.push({{
              id: parseInt(edgeId),
              color: original.color,
              width: original.width
            }});
          }});
          edges.update(edgeUpdates);
          
          // Reset info display
          var infoElement = document.getElementById('info');
          infoElement.innerHTML = '';
          infoElement.classList.remove('show');
        }}
        
        // Map unlocking functionality with 'U' key
        var mapLocked = false;
        // Always listen for keydown events, even if overlays are open
        window.addEventListener('keydown', function(e) {{
          if (e.key && e.key.toLowerCase() === 'u') {{
            mapLocked = !mapLocked;
            if (mapLocked) {{
              network.setOptions({{
                interaction: {{
                  dragView: false,
                  zoomView: false,
                  hover: false,
                  selectConnectedEdges: false,
                  hoverConnectedEdges: false,
                  multiselect: false,
                  navigationButtons: false
                }}
              }});
              document.body.style.cursor = 'not-allowed';
              console.log('Map locked - press U to unlock');
            }} else {{
              network.setOptions({{
                interaction: {{
                  dragView: true,
                  zoomView: true,
                  hover: true,
                  selectConnectedEdges: true,
                  hoverConnectedEdges: true,
                  multiselect: true
                }}
              }});
              document.body.style.cursor = 'default';
              console.log('Map unlocked - press U to lock');
              // Restore hover highlighting if a node is selected
              network.setOptions({{
                interaction: {{
                  hover: true,
                  hoverConnectedEdges: true
                }}
              }});
              if (selectedNodeId !== null) {{
                highlightNodeAndEdges(selectedNodeId);
              }}
            }}
          }}
        }});
        
        // Make instruction overlay dismissible
        var instructionOverlay = document.getElementById('instruction-overlay');
        instructionOverlay.addEventListener('click', function() {{
          instructionOverlay.style.display = 'none';
        }});

        // Add small circular recenter button to bottom right
        var recenterButton = document.createElement('button');
        recenterButton.title = 'Recenter to start node';
        recenterButton.innerHTML = '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="14" cy="14" r="12" stroke="#1e40af" stroke-width="2" fill="#e0e7ff"/><circle cx="14" cy="14" r="5" stroke="#1e40af" stroke-width="2" fill="none"/><circle cx="14" cy="14" r="2" fill="#1e40af"/></svg>';
        recenterButton.style.position = 'fixed';
        recenterButton.style.bottom = '32px';
        recenterButton.style.right = '32px';
        recenterButton.style.zIndex = '1002';
        recenterButton.style.width = '40px';
        recenterButton.style.height = '40px';
        recenterButton.style.borderRadius = '50%';
        recenterButton.style.border = 'none';
        recenterButton.style.background = 'transparent';
        recenterButton.style.boxShadow = '0 2px 8px rgba(0,0,0,0.10)';
        recenterButton.style.display = 'flex';
        recenterButton.style.alignItems = 'center';
        recenterButton.style.justifyContent = 'center';
        recenterButton.style.cursor = 'pointer';
        recenterButton.style.transition = 'box-shadow 0.2s';
        recenterButton.onmouseover = function() {{ recenterButton.style.boxShadow = '0 4px 16px rgba(59,130,246,0.18)'; }};
        recenterButton.onmouseout = function() {{ recenterButton.style.boxShadow = '0 2px 8px rgba(0,0,0,0.10)'; }};
        document.body.appendChild(recenterButton);

        recenterButton.addEventListener('click', function() {{
          if ({start_node}) {{
            network.focus({start_node}, {{
              scale: 1.0,
              offset: {{x: 0, y: 0}},
              animation: {{
                duration: 800,
                easingFunction: 'easeInOutQuad'
              }}
            }});
            network.selectNodes([{start_node}]);
            highlightNodeAndEdges({start_node});
          }}
        }});

        // Show statistics panel at top center for a brief time on load
        var topStatsPanel = document.createElement('div');
        topStatsPanel.style.position = 'fixed';
        topStatsPanel.style.top = '32px';
        topStatsPanel.style.left = '50%';
        topStatsPanel.style.transform = 'translateX(-50%)';
        topStatsPanel.style.zIndex = '1003';
        topStatsPanel.style.background = 'rgba(255,255,255,0.98)';
        topStatsPanel.style.borderRadius = '16px';
        topStatsPanel.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)';
        topStatsPanel.style.padding = '12px 28px';
        topStatsPanel.style.fontSize = '16px';
        topStatsPanel.style.color = '#334155';
        topStatsPanel.style.fontWeight = '600';
        topStatsPanel.style.textAlign = 'center';
        topStatsPanel.innerHTML = 'Loaded <span style="color:#1e40af">' + nodes.length + '</span> nodes & <span style="color:#e57373">' + edges.length + '</span> links';
        document.body.appendChild(topStatsPanel);
        setTimeout(function() {{
          topStatsPanel.style.transition = 'opacity 0.6s';
          topStatsPanel.style.opacity = '0';
          setTimeout(function() {{ topStatsPanel.remove(); }}, 700);
        }}, 3000);
      </script>
    </body>
    </html>
    """

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Interactive HTML graph written to: {output_html}")

def resolve_start_node(start_value, nodes, original_nodes):
    # Try to interpret as int
    try:
        return int(start_value)
    except ValueError:
        pass
    # Try to match label (case-insensitive, exact match)
    for nid, label in original_nodes.items():
        if label.strip().lower() == start_value.strip().lower():
            return nid
    raise ValueError(f"Could not resolve start node: '{start_value}'. Use a valid node ID or label.")

def main():
  ap = argparse.ArgumentParser(
    description="Filter and visualize reachability graph.\n"
          "Input can be provided as a file or piped via stdin.\n"
          "Examples:\n"
          "  python3 reachability_viz.py input.dot --start NODE_ID\n"
          "  cat input.dot | python3 reachability_viz.py --start NODE_ID\n"
  )
  ap.add_argument('input', nargs='?', default=None,
    help='Path to DOT-like input file. If omitted, reads from stdin. Use piping for large files or automation.')
  ap.add_argument('--start', required=True, help='Start node id or label')
  ap.add_argument('--depth', type=int, default=2, help='Number of hops from start (default: 2)')
  ap.add_argument('--direction', choices=['out', 'in', 'both'], default='both', help='BFS direction (default: both)')
  ap.add_argument('--rankdir', choices=['TB', 'LR', 'BT', 'RL'], default='TB', help='Hierarchical direction')
  ap.add_argument('--edge-labels', choices=['status', 'full', 'none'], default='status', help='Edge label detail')
  ap.add_argument('--enabled-only', action='store_true', help='Include only edges with status E')
  ap.add_argument('--output', default='reachability_view.dot', help='Output DOT path')
  ap.add_argument('--render', choices=['png', 'svg'], help='Also render an image with Graphviz')
  ap.add_argument('--layout', default='dot', help='Graphviz layout engine (default: dot)')
  ap.add_argument('--html', nargs='?', const='reachability.html', default='reachability.html', help='Also export an interactive HTML graph (default: reachability.html)')

  ap.add_argument('--splines', choices=['curved','ortho','polyline','line','spline','true','false'], default='curved')
  ap.add_argument('--no-overlap', action='store_true', default=True)
  ap.add_argument('--allow-overlap', dest='no_overlap', action='store_false')
  ap.add_argument('--concentrate', action='store_true')
  ap.add_argument('--nodesep', type=float, default=0.35)
  ap.add_argument('--ranksep', type=float, default=0.6)
  ap.add_argument('--ports', action='store_true')
  ap.add_argument('--level-edges-only', action='store_true')
  ap.add_argument('--deemphasize-cross', action='store_true', default=True)
  ap.add_argument('--no-deemphasize-cross', dest='deemphasize_cross', action='store_false')

  args = ap.parse_args()

  # If no input argument, read from stdin
  if args.input is None:
    if sys.stdin.isatty():
      print("Error: No input provided via stdin. Pipe a DOT file or specify a file path.", file=sys.stderr)
      sys.exit(1)
    source_text = sys.stdin.read()
  else:
    with open(args.input, 'r', encoding='utf-8', errors='ignore') as f:
      source_text = f.read()

  nodes, edges, original_nodes = parse_source_text(source_text)
  if args.enabled_only:
      edges = [e for e in edges if e['status'] == 'E']

  try:
      start_node = resolve_start_node(args.start, nodes, original_nodes)
  except Exception as e:
      print(str(e), file=sys.stderr)
      sys.exit(1)

  out_adj, in_adj = build_adjacency(edges)
  levels, included_nodes = bfs_levels(start_node, args.depth, out_adj, in_adj, args.direction)
  filtered_edges = [e for e in edges if e["src"] in included_nodes and e["dst"] in included_nodes]
  
  # Merge bidirectional edges to avoid duplicate connections
  filtered_edges = merge_bidirectional_edges(filtered_edges)

  # Split wide levels into sub-levels of max 50 nodes and assign levels to nodes
  def split_levels(levels, max_per_level=50):
      new_levels = []
      node_levels = {}
      level_idx = 0
      for group in levels:
          group = list(group)
          for i in range(0, len(group), max_per_level):
              sub_group = set(group[i:i+max_per_level])
              new_levels.append(sub_group)
              for nid in sub_group:
                  node_levels[nid] = level_idx
              level_idx += 1
      return new_levels, node_levels
  levels, node_levels = split_levels(levels, max_per_level=20)

  dot_text = generate_dot(
      nodes, filtered_edges, included_nodes, levels, start_node,
      rankdir=args.rankdir, edge_labels=args.edge_labels,
      splines=args.splines, no_overlap=args.no_overlap, concentrate=args.concentrate,
      nodesep=args.nodesep, ranksep=args.ranksep, use_ports=args.ports,
      level_edges_only=args.level_edges_only, deemphasize_cross=args.deemphasize_cross
  )

  with open(args.output, 'w', encoding='utf-8') as f:
      f.write(dot_text)
  print(f"Wrote DOT to: {args.output}")

  if args.render:
      out_img = render_with_graphviz(args.output, out_format=args.render, layout=args.layout)
      if out_img:
          print(f"Rendered image: {out_img}")

  if args.html:
      export_html(nodes, filtered_edges, included_nodes, args.html, start_node, original_nodes, levels, node_levels)

if __name__ == '__main__':
    main()
