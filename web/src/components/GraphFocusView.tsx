import { useMemo } from "react";
import type { GraphEdge, GraphEntity } from "../api/types";

type GraphFocusViewProps = {
  center: GraphEntity;
  entities: GraphEntity[];
  edges: GraphEdge[];
  selectedId?: string | null;
  isLoading?: boolean;
  onSelect: (entityId: string) => void;
};

type LayoutNode = GraphEntity & {
  x: number;
  y: number;
  radius: number;
  role: "center" | "neighbor";
};

const VIEW_WIDTH = 680;
const VIEW_HEIGHT = 380;
const CENTER_RADIUS = 34;
const NEIGHBOR_RADIUS = 28;

function edgeKey(edge: GraphEdge): string {
  return `${edge.src}|${edge.predicate}|${edge.dst}`;
}

function buildLayout(center: GraphEntity, neighbors: GraphEntity[]): LayoutNode[] {
  const centerNode: LayoutNode = {
    ...center,
    x: VIEW_WIDTH / 2,
    y: VIEW_HEIGHT / 2,
    radius: CENTER_RADIUS,
    role: "center",
  };
  if (neighbors.length === 0) {
    return [centerNode];
  }

  const orbit = Math.min(VIEW_WIDTH, VIEW_HEIGHT) * 0.34;
  const neighborNodes = neighbors.map((entity, index) => {
    const angle = (Math.PI * 2 * index) / neighbors.length - Math.PI / 2;
    return {
      ...entity,
      x: centerNode.x + Math.cos(angle) * orbit,
      y: centerNode.y + Math.sin(angle) * orbit,
      radius: NEIGHBOR_RADIUS,
      role: "neighbor" as const,
    };
  });
  return [centerNode, ...neighborNodes];
}

function buildEdgePath(source: LayoutNode, target: LayoutNode): { path: string; labelX: number; labelY: number } {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.hypot(dx, dy) || 1;
  const unitX = dx / distance;
  const unitY = dy / distance;
  const startX = source.x + unitX * (source.radius + 8);
  const startY = source.y + unitY * (source.radius + 8);
  const endX = target.x - unitX * (target.radius + 8);
  const endY = target.y - unitY * (target.radius + 8);
  const midX = (startX + endX) / 2;
  const midY = (startY + endY) / 2;
  const curveOffset = Math.min(36, distance * 0.15);
  const ctrlX = midX - unitY * curveOffset;
  const ctrlY = midY + unitX * curveOffset;
  return {
    path: `M ${startX} ${startY} Q ${ctrlX} ${ctrlY} ${endX} ${endY}`,
    labelX: ctrlX,
    labelY: ctrlY,
  };
}

export function GraphFocusView({
  center,
  entities,
  edges,
  selectedId = null,
  isLoading = false,
  onSelect,
}: GraphFocusViewProps) {
  const nodeById = useMemo(() => new Map(entities.map((entity) => [entity.id, entity])), [entities]);
  const layoutNodes = useMemo(() => {
    const neighbors = entities.filter((entity) => entity.id !== center.id);
    return buildLayout(center, neighbors);
  }, [center, entities]);
  const layoutById = useMemo(() => new Map(layoutNodes.map((node) => [node.id, node])), [layoutNodes]);

  const visibleEdges = useMemo(() => {
    const unique = new Map<string, GraphEdge>();
    for (const edge of edges) {
      if (edge.src !== center.id && edge.dst !== center.id) {
        continue;
      }
      if (!layoutById.has(edge.src) || !layoutById.has(edge.dst)) {
        continue;
      }
      unique.set(edgeKey(edge), edge);
    }
    return Array.from(unique.values());
  }, [center.id, edges, layoutById]);

  return (
    <section className="graph-focus-view" aria-label="节点关联视图">
      <div className="graph-focus-header">
        <h3>关联视图</h3>
        <p>
          中心节点「{center.name}」及 {Math.max(entities.length - 1, 0)} 个直接关联实体，共 {visibleEdges.length} 条关系
        </p>
      </div>

      {isLoading ? <p role="status">正在加载关联节点…</p> : null}

      {!isLoading ? (
        <svg
          className="graph-focus-canvas"
          width={VIEW_WIDTH}
          height={VIEW_HEIGHT}
          viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
          role="img"
          aria-label={`${center.name} 的关联子图`}
        >
          <defs>
            <linearGradient id="focus-edge-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#2563eb" />
              <stop offset="100%" stopColor="#14b8a6" />
            </linearGradient>
            <marker id="focus-graph-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#0891b2" />
            </marker>
          </defs>
          {visibleEdges.map((edge) => {
            const source = layoutById.get(edge.src);
            const target = layoutById.get(edge.dst);
            if (!source || !target) {
              return null;
            }
            const geometry = buildEdgePath(source, target);
            const label = edge.predicate.length > 10 ? `${edge.predicate.slice(0, 10)}…` : edge.predicate;
            const labelWidth = Math.max(56, label.length * 11 + 18);
            const edgeActive =
              selectedId === null ||
              edge.src === selectedId ||
              edge.dst === selectedId ||
              selectedId === center.id;
            return (
              <g
                key={edgeKey(edge)}
                className={edgeActive ? "graph-focus-edge-group active" : "graph-focus-edge-group dimmed"}
              >
                <path d={geometry.path} className="graph-focus-edge" markerEnd="url(#focus-graph-arrow)" />
                <rect
                  x={geometry.labelX - labelWidth / 2}
                  y={geometry.labelY - 10}
                  width={labelWidth}
                  height={20}
                  rx={10}
                  className="graph-focus-edge-label-bg"
                />
                <text x={geometry.labelX} y={geometry.labelY + 3} className="graph-focus-edge-label">
                  {label}
                </text>
                <title>{`${edge.src_name} → ${edge.predicate} → ${edge.dst_name}`}</title>
              </g>
            );
          })}
          {layoutNodes.map((node) => {
            const isCenter = node.role === "center";
            const isSelected = node.id === selectedId;
            const isLinked = !isCenter && (selectedId === center.id || selectedId === node.id);
            const nodeClass = isCenter
              ? "graph-focus-node center"
              : isSelected
                ? "graph-focus-node selected"
                : isLinked
                  ? "graph-focus-node linked"
                  : "graph-focus-node";
            return (
              <g key={node.id} transform={`translate(${node.x}, ${node.y})`} className={nodeClass} onClick={() => onSelect(node.id)}>
                {isCenter || isSelected ? <circle className="graph-focus-node-halo" r={node.radius + 7} /> : null}
                {isLinked && !isSelected ? <circle className="graph-focus-node-halo linked" r={node.radius + 5} /> : null}
                <circle r={node.radius} />
                <text className="graph-focus-node-label" dy="0.35em">
                  {node.name.length > 10 ? `${node.name.slice(0, 10)}…` : node.name}
                </text>
                <title>{`${node.name} (${node.type})`}</title>
              </g>
            );
          })}
        </svg>
      ) : null}

      {!isLoading && visibleEdges.length > 0 ? (
        <ul className="graph-focus-edge-list">
          {visibleEdges.map((edge) => (
            <li key={edgeKey(edge)}>
              <strong>{nodeById.get(edge.src)?.name ?? edge.src_name}</strong>
              <span>{edge.predicate}</span>
              <strong>{nodeById.get(edge.dst)?.name ?? edge.dst_name}</strong>
            </li>
          ))}
        </ul>
      ) : null}

      {!isLoading && visibleEdges.length === 0 ? (
        <p className="graph-focus-empty">该节点暂无已加载的直接关联关系，可点击「展开邻居」继续探索。</p>
      ) : null}
    </section>
  );
}
