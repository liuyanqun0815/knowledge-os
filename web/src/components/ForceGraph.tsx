import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphEdge, GraphEntity } from "../api/types";

export type ForceGraphNode = GraphEntity & {
  x: number;
  y: number;
  vx: number;
  vy: number;
};

type ForceGraphProps = {
  entities: GraphEntity[];
  edges: GraphEdge[];
  selectedId: string | null;
  highlightEdgeKeys?: Set<string>;
  onSelect: (entityId: string) => void;
  onDeselect?: () => void;
  onExpand: (entityId: string) => void;
};

const NODE_RADIUS = 26;
const EDGE_PAD = 8;

function edgeKey(edge: GraphEdge): string {
  return `${edge.src}|${edge.predicate}|${edge.dst}`;
}

type EdgeGeometry = {
  path: string;
  labelX: number;
  labelY: number;
};

function buildEdgeGeometry(source: ForceGraphNode, target: ForceGraphNode): EdgeGeometry {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.hypot(dx, dy) || 1;
  const unitX = dx / distance;
  const unitY = dy / distance;
  const startX = source.x + unitX * (NODE_RADIUS + EDGE_PAD);
  const startY = source.y + unitY * (NODE_RADIUS + EDGE_PAD);
  const endX = target.x - unitX * (NODE_RADIUS + EDGE_PAD);
  const endY = target.y - unitY * (NODE_RADIUS + EDGE_PAD);
  const midX = (startX + endX) / 2;
  const midY = (startY + endY) / 2;
  const curveOffset = Math.min(48, distance * 0.22);
  const ctrlX = midX - unitY * curveOffset;
  const ctrlY = midY + unitX * curveOffset;
  return {
    path: `M ${startX} ${startY} Q ${ctrlX} ${ctrlY} ${endX} ${endY}`,
    labelX: ctrlX,
    labelY: ctrlY,
  };
}

function createNode(entity: GraphEntity, width: number, height: number, anchor?: ForceGraphNode): ForceGraphNode {
  if (anchor) {
    const angle = Math.random() * Math.PI * 2;
    return {
      ...entity,
      x: anchor.x + Math.cos(angle) * 120,
      y: anchor.y + Math.sin(angle) * 120,
      vx: 0,
      vy: 0,
    };
  }
  return {
    ...entity,
    x: width / 2 + (Math.random() - 0.5) * width * 0.72,
    y: height / 2 + (Math.random() - 0.5) * height * 0.72,
    vx: 0,
    vy: 0,
  };
}

function simulate(nodes: ForceGraphNode[], edges: GraphEdge[], width: number, height: number): void {
  const alpha = 0.35;
  const centerX = width / 2;
  const centerY = height / 2;
  const nodeById = new Map(nodes.map((node) => [node.id, node]));

  for (let i = 0; i < nodes.length; i += 1) {
    for (let j = i + 1; j < nodes.length; j += 1) {
      const left = nodes[i];
      const right = nodes[j];
      const dx = right.x - left.x;
      const dy = right.y - left.y;
      const distance = Math.hypot(dx, dy) || 1;
      const force = (900 / (distance * distance)) * alpha;
      const fx = (dx / distance) * force;
      const fy = (dy / distance) * force;
      left.vx -= fx;
      left.vy -= fy;
      right.vx += fx;
      right.vy += fy;
    }
  }

  for (const edge of edges) {
    const source = nodeById.get(edge.src);
    const target = nodeById.get(edge.dst);
    if (!source || !target) {
      continue;
    }
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const distance = Math.hypot(dx, dy) || 1;
    const force = (distance - 130) * 0.05 * alpha;
    const fx = (dx / distance) * force;
    const fy = (dy / distance) * force;
    source.vx += fx;
    source.vy += fy;
    target.vx -= fx;
    target.vy -= fy;
  }

  for (const node of nodes) {
    node.vx += (centerX - node.x) * 0.008 * alpha;
    node.vy += (centerY - node.y) * 0.008 * alpha;
    node.vx *= 0.84;
    node.vy *= 0.84;
    node.x += node.vx;
    node.y += node.vy;
    node.x = Math.max(NODE_RADIUS, Math.min(width - NODE_RADIUS, node.x));
    node.y = Math.max(NODE_RADIUS, Math.min(height - NODE_RADIUS, node.y));
  }
}

export function ForceGraph({
  entities,
  edges,
  selectedId,
  highlightEdgeKeys,
  onSelect,
  onDeselect,
  onExpand,
}: ForceGraphProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 720, height: 480 });
  const [nodes, setNodes] = useState<ForceGraphNode[]>([]);
  const nodesRef = useRef<ForceGraphNode[]>([]);
  const edgesRef = useRef<GraphEdge[]>([]);
  const frameRef = useRef<number | null>(null);
  const selectedIdRef = useRef<string | null>(selectedId);
  selectedIdRef.current = selectedId;

  const edgeList = useMemo(() => {
    const unique = new Map<string, GraphEdge>();
    for (const edge of edges) {
      unique.set(edgeKey(edge), edge);
    }
    return Array.from(unique.values());
  }, [edges]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      setSize({
        width: Math.max(320, Math.floor(entry.contentRect.width)),
        height: Math.max(360, Math.floor(entry.contentRect.height)),
      });
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    edgesRef.current = edgeList;
    const existing = new Map(nodesRef.current.map((node) => [node.id, node]));
    const anchor = selectedIdRef.current ? existing.get(selectedIdRef.current) : undefined;
    const nextNodes = entities.map((entity) => {
      const current = existing.get(entity.id);
      if (current) {
        return { ...current, ...entity };
      }
      return createNode(entity, size.width, size.height, anchor);
    });
    nodesRef.current = nextNodes;
    setNodes(nextNodes);
  }, [entities, edgeList, size.width, size.height]);

  useEffect(() => {
    const tick = () => {
      if (nodesRef.current.length > 0) {
        simulate(nodesRef.current, edgesRef.current, size.width, size.height);
        setNodes([...nodesRef.current]);
      }
      frameRef.current = window.requestAnimationFrame(tick);
    };
    frameRef.current = window.requestAnimationFrame(tick);
    return () => {
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
      }
    };
  }, [size.width, size.height]);

  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);

  const connectedNodeIds = useMemo(() => {
    if (!selectedId) {
      return new Set<string>();
    }
    const ids = new Set<string>([selectedId]);
    for (const edge of edgeList) {
      if (edge.src === selectedId || edge.dst === selectedId) {
        ids.add(edge.src);
        ids.add(edge.dst);
      }
    }
    return ids;
  }, [edgeList, selectedId]);

  const hasSelection = selectedId !== null;

  return (
    <div ref={containerRef} className="force-graph-shell">
      <svg
        className="force-graph"
        width={size.width}
        height={size.height}
        viewBox={`0 0 ${size.width} ${size.height}`}
        role="img"
        aria-label="知识图谱力导向图"
      >
        <defs>
          <linearGradient id="graph-edge-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#2563eb" />
            <stop offset="100%" stopColor="#0891b2" />
          </linearGradient>
          <filter id="graph-edge-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="1" stdDeviation="2" floodColor="#2563eb" floodOpacity="0.35" />
          </filter>
          <marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" fill="#0891b2" />
          </marker>
          <marker id="graph-arrow-muted" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 Z" fill="#94a3b8" />
          </marker>
        </defs>
        <rect
          className="force-graph-bg"
          width={size.width}
          height={size.height}
          fill="transparent"
          onClick={() => onDeselect?.()}
        />
        {edgeList.map((edge) => {
          const source = nodeById.get(edge.src);
          const target = nodeById.get(edge.dst);
          if (!source || !target) {
            return null;
          }
          const geometry = buildEdgeGeometry(source, target);
          const connectedToSelected =
            selectedId !== null && (edge.src === selectedId || edge.dst === selectedId);
          const isHighlighted = connectedToSelected || highlightEdgeKeys?.has(edgeKey(edge)) === true;
          const isDimmed = hasSelection && !isHighlighted;
          const label = edge.predicate.length > 8 ? `${edge.predicate.slice(0, 8)}…` : edge.predicate;
          const labelWidth = Math.max(52, label.length * 11 + 18);
          const groupClass = isHighlighted
            ? "force-graph-edge-group active"
            : isDimmed
              ? "force-graph-edge-group dimmed"
              : "force-graph-edge-group";
          return (
            <g key={edgeKey(edge)} className={groupClass}>
              <path
                d={geometry.path}
                className="force-graph-edge"
                markerEnd={isHighlighted ? "url(#graph-arrow)" : "url(#graph-arrow-muted)"}
              />
              <rect
                x={geometry.labelX - labelWidth / 2}
                y={geometry.labelY - 10}
                width={labelWidth}
                height={20}
                rx={10}
                className="force-graph-edge-label-bg"
              />
              <text x={geometry.labelX} y={geometry.labelY + 3} className="force-graph-edge-label">
                {label}
              </text>
              <title>{`${edge.src_name} → ${edge.predicate} → ${edge.dst_name}`}</title>
            </g>
          );
        })}
        {nodes.map((node) => {
          const selected = node.id === selectedId;
          const linked = hasSelection && connectedNodeIds.has(node.id) && !selected;
          const dimmed = hasSelection && !connectedNodeIds.has(node.id);
          const nodeClass = selected
            ? "force-graph-node selected"
            : linked
              ? "force-graph-node linked"
              : dimmed
                ? "force-graph-node dimmed"
                : "force-graph-node";
          return (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              className={nodeClass}
              onClick={(event) => {
                event.stopPropagation();
                onSelect(node.id);
              }}
              onDoubleClick={(event) => {
                event.stopPropagation();
                onExpand(node.id);
              }}
            >
              {selected ? <circle className="force-graph-node-halo" r={NODE_RADIUS + 8} /> : null}
              {linked ? <circle className="force-graph-node-halo linked" r={NODE_RADIUS + 6} /> : null}
              <circle r={NODE_RADIUS} />
              <text className="force-graph-node-label" dy="0.35em">
                {node.name.length > 8 ? `${node.name.slice(0, 8)}…` : node.name}
              </text>
              <title>{`${node.name} (${node.type})`}</title>
            </g>
          );
        })}
      </svg>
      <p className="force-graph-hint">单击选中节点，单击空白处取消选中；双击或点击「展开邻居」扩展关联。</p>
    </div>
  );
}
