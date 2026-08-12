#!/usr/bin/env python3
"""
scientella-knowledge 知识图谱状态图生成脚本

用法：
    python3 scripts/knowledge-graph.py <vault路径>

输出：
    .scientella/graph.json（位于 vault 根目录下）

每次发出会影响知识库的处理请求时，固定执行此脚本。
脚本仅读取文件，不做任何修改。
"""

import json
import os
import re
import sys
import yaml


def parse_frontmatter(text):
    """提取 YAML frontmatter 中的 tags 和 aliases，返回 (tags, aliases)。"""
    if not text.startswith('---'):
        return [], []
    end = text.find('---', 3)
    if end == -1:
        return [], []
    try:
        fm = yaml.safe_load(text[3:end])
    except Exception:
        return [], []
    if fm is None:
        return [], []
    tags = fm.get('tags', []) or []
    aliases = fm.get('aliases', []) or []
    return tags, aliases


def extract_outbound_links(text):
    """提取正文中所有 [[wikilink]] 的目标名（剔除 # 和 ^ 引用）。"""
    links = set()
    # 匹配 [[...]]，处理别名格式 [[target|display]]
    for m in re.finditer(r'\[\[([^\]|#^]+)(?:[|][^\]]+)?\]\]', text):
        target = m.group(1).strip()
        # 跳过空的
        if target:
            links.add(target)
    return links


def build_graph(vault_path):
    """扫描 vault 下所有 .md 文件，构建图结构。"""
    nodes = {}
    parse_errors = []
    has_any_wikilinks = False
    
    # Pass 1: parse each file
    for root, dirs, files in os.walk(vault_path):
        # Skip all dot-directories (.scientella 为元数据目录，其下 config.md/VAULT.md 非知识节点)
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for fname in files:
            if not fname.endswith('.md'):
                continue
            
            fpath = os.path.join(root, fname)
            relpath = os.path.relpath(fpath, vault_path)
            node_name = os.path.splitext(fname)[0]  # filename without .md
            
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    text = f.read()
            except Exception as e:
                parse_errors.append({'file': os.path.relpath(fpath, vault_path), 'error': f'Read error: {str(e)}'})
                continue
            
            tags, aliases = parse_frontmatter(text)
            outbound = extract_outbound_links(text)
            
            if outbound:
                has_any_wikilinks = True
            
            nodes[node_name] = {
                'file': relpath,
                'tags': tags,
                'aliases': aliases,
                'total_chars': len(text),  # 卡片文件总字符数（含 frontmatter）
                'outbound': sorted(outbound),
                'inbound': [],  # filled in next pass
            }
    
    if not has_any_wikilinks:
        return {
            'has_wikilinks': False,
            'node_count': len(nodes),
            'nodes': {},
            'parse_errors': parse_errors,
        }
    
    # Pass 2: compute inbound links
    # A link from A to B → B.inbound.append(A)
    # Also match aliases: if A links to "XX" and node C has alias "XX", then C.inbound.append(A)
    name_to_nodes = {}  # name/alias → set of node names
    for name, data in nodes.items():
        if name not in name_to_nodes:
            name_to_nodes[name] = set()
        name_to_nodes[name].add(name)
        for alias in data['aliases']:
            if alias not in name_to_nodes:
                name_to_nodes[alias] = set()
            name_to_nodes[alias].add(name)
    
    for src_name, src_data in nodes.items():
        for target in src_data['outbound']:
            # Try direct name match
            if target in nodes:
                nodes[target]['inbound'].append(src_name)
            # Try alias match
            elif target in name_to_nodes:
                for real_name in name_to_nodes[target]:
                    if real_name in nodes and src_name not in nodes[real_name]['inbound']:
                        nodes[real_name]['inbound'].append(src_name)
            # target not found → leave inbound empty (dead link)
    
    # Clean up inbound lists
    for n in nodes:
        nodes[n]['inbound'] = sorted(set(nodes[n]['inbound']))
    
    # Build summary
    node_summaries = {}
    for name, data in nodes.items():
        node_summaries[name] = {
            'file': data['file'],
            'tags': data['tags'],
            'aliases': data['aliases'],
            'total_chars': data['total_chars'],
            'outbound': data['outbound'],
            'inbound': data['inbound'],
            'total_edges': len(data['outbound']) + len(data['inbound']),
        }
    
    return {
        'has_wikilinks': True,
        'node_count': len(nodes),
        'nodes': node_summaries,
        'parse_errors': parse_errors,
    }


def compute_components(graph):
    """计算无向连通块，返回各块大小及最大度节点（用于判定网络主题）。"""
    if not graph['has_wikilinks'] or not graph['nodes']:
        return []
    
    # Build undirected adjacency
    adj = {name: set() for name in graph['nodes']}
    for name, data in graph['nodes'].items():
        for target in data['outbound']:
            if target in adj:
                adj[name].add(target)
                adj[target].add(name)
    
    visited = set()
    components = []
    
    for start in adj:
        if start in visited:
            continue
        # BFS
        queue = [start]
        visited.add(start)
        comp = set()
        while queue:
            node = queue.pop(0)
            comp.add(node)
            for nb in adj[node]:
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        
        # Component stats
        max_deg_node = max(comp, key=lambda n: len(adj[n]), default=start)
        components.append({
            'size': len(comp),
            'max_degree_node': max_deg_node,
            'max_degree': len(adj[max_deg_node]),
        })
    
    # Sort by size descending
    components.sort(key=lambda c: c['size'], reverse=True)
    return components


def main():
    # 确保 Windows 默认 GBK 控制台下中文和特殊字符能正常输出
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        pass

    if len(sys.argv) < 2:
        print('Usage: python3 scripts/knowledge-graph.py <vault_path>')
        sys.exit(1)
    
    vault_path = sys.argv[1]
    if not os.path.isdir(vault_path):
        print(f'Error: {vault_path} is not a valid directory')
        sys.exit(1)
    
    graph = build_graph(vault_path)

    # Compute aggregated metadata
    total_edges = 0
    isolated = []
    dead_links = {}
    if graph['has_wikilinks']:
        total_edges = sum(n['total_edges'] for n in graph['nodes'].values())
        for name, data in graph['nodes'].items():
            if data['total_edges'] == 0:
                isolated.append(name)
            dead = [t for t in data['outbound'] if t not in graph['nodes'] and not any(t in graph['nodes'][n].get('aliases',[]) for n in graph['nodes'])]
            if dead:
                dead_links[name] = dead

    graph['total_edges'] = total_edges
    graph['isolated_nodes'] = isolated
    graph['dead_links'] = dead_links

    # --- 连通块统计 ---
    graph['connected_components'] = compute_components(graph)

    # Ensure .scientella directory exists
    scientella_dir = os.path.join(vault_path, '.scientella')
    os.makedirs(scientella_dir, exist_ok=True)

    out_path = os.path.join(scientella_dir, 'graph.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    # Concise stdout for Agent consumption
    print(f'{graph["node_count"]} nodes, {total_edges} edges')
    if graph.get('parse_errors'):
        print(f'解析错误 ({len(graph["parse_errors"])}): ' + '; '.join(e["file"] + ': ' + e["error"] for e in graph['parse_errors']))
    if isolated:
        print(f'孤立节点 ({len(isolated)}): ' + ', '.join(isolated))
    if dead_links:
        items = [f'{s} → {t}' for s, ts in sorted(dead_links.items()) for t in ts]
        print(f'死链 ({len(items)}): ' + '; '.join(items))
    if graph.get('connected_components'):
        comps = graph['connected_components']
        print(f'连通块 ({len(comps)}): ' + ', '.join(
            f'{c["size"]}n({c["max_degree_node"]})' for c in comps[:8]
        ) + (' ...' if len(comps) > 8 else ''))

    if isolated or dead_links:
        sys.exit(1)


if __name__ == '__main__':
    main()
