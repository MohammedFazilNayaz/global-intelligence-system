import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { api } from '../api/client';
import type {
  KnowledgeGraphResponse,
  GraphNode,
  GraphEdge,
  PaginatedRelationships,
  Entity,
} from '../types/intelligence';

interface KnowledgeGraphViewProps {
  onSelectEntity?: (entityId: string) => void;
  initialEntityId?: string;
}

export const KnowledgeGraphView: React.FC<KnowledgeGraphViewProps> = ({
  onSelectEntity,
  initialEntityId,
}) => {
  const [viewMode, setViewMode] = useState<'graph' | 'ledger'>('graph');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [depth, setDepth] = useState<number>(1);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Subgraph state
  const [graphData, setGraphData] = useState<KnowledgeGraphResponse | null>(null);
  const [centerEntityId, setCenterEntityId] = useState<string | null>(initialEntityId || null);

  // Suggested / available entities for quick selection
  const [sampleEntities, setSampleEntities] = useState<Entity[]>([]);

  // Relationship Ledger state
  const [ledgerData, setLedgerData] = useState<PaginatedRelationships | null>(null);
  const [ledgerPage, setLedgerPage] = useState<number>(1);
  const [ledgerFilterType, setLedgerFilterType] = useState<string>('');

  // Initial load: fetch entities for quick selection
  useEffect(() => {
    async function loadSamples() {
      try {
        const res = await api.getEntities({ limit: 10 });
        setSampleEntities(res.items);
        if (!centerEntityId && res.items.length > 0) {
          setCenterEntityId(res.items[0].id);
        }
      } catch (e) {
        console.error('Failed to load sample entities', e);
      }
    }
    loadSamples();
  }, []);

  // Fetch subgraph when centerEntityId or depth changes
  const loadGraph = useCallback(async () => {
    if (!centerEntityId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getEntityGraph(centerEntityId, depth, 3, 50);
      setGraphData(data);
      // If a selected node is no longer in nodes, select center node
      const center = data.nodes.find((n) => n.id === data.center_node_id);
      setSelectedNode(center || data.nodes[0] || null);
      setSelectedEdge(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load knowledge graph';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [centerEntityId, depth]);

  useEffect(() => {
    if (viewMode === 'graph' && centerEntityId) {
      loadGraph();
    }
  }, [viewMode, centerEntityId, depth, loadGraph]);

  // Load ledger when in ledger mode
  const loadLedger = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getRelationships({
        page: ledgerPage,
        page_size: 15,
        relationship_type: ledgerFilterType || undefined,
      });
      setLedgerData(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load relationship ledger';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [ledgerPage, ledgerFilterType]);

  useEffect(() => {
    if (viewMode === 'ledger') {
      loadLedger();
    }
  }, [viewMode, ledgerPage, ledgerFilterType, loadLedger]);

  // Handle graph text search
  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.searchGraph(searchQuery.trim(), depth, 50);
      setGraphData(res);
      if (res.nodes.length > 0) {
        setSelectedNode(res.nodes[0]);
        setCenterEntityId(res.center_node_id || res.nodes[0].id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Search failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Node layout calculation (radial circular layout for deterministic beauty)
  const nodePositions = useMemo(() => {
    if (!graphData || graphData.nodes.length === 0) return new Map<string, { x: number; y: number }>();
    const pos = new Map<string, { x: number; y: number }>();
    const centerId = graphData.center_node_id;

    const width = 800;
    const height = 500;
    const cx = width / 2;
    const cy = height / 2;

    pos.set(centerId, { x: cx, y: cy });

    const otherNodes = graphData.nodes.filter((n) => n.id !== centerId);
    const radius = depth === 1 ? 160 : depth === 2 ? 180 : 210;
    const angleStep = (2 * Math.PI) / Math.max(1, otherNodes.length);

    otherNodes.forEach((node, i) => {
      const angle = i * angleStep;
      // Add subtle radial variation for higher depth to avoid clutter
      const r = radius + (i % 2 === 0 ? 25 : -25);
      pos.set(node.id, {
        x: cx + r * Math.cos(angle),
        y: cy + r * Math.sin(angle),
      });
    });

    return pos;
  }, [graphData, depth]);

  const getNodeColor = (entityType: string) => {
    const t = entityType.toUpperCase();
    if (t.includes('CENTRAL_BANK') || t.includes('BANK')) return '#f59e0b';
    if (t.includes('COUNTRY') || t.includes('GOVERNMENT')) return '#3b82f6';
    if (t.includes('COMPANY') || t.includes('ORGANIZATION')) return '#10b981';
    if (t.includes('PERSON')) return '#8b5cf6';
    if (t.includes('CURRENCY') || t.includes('COMMODITY')) return '#ec4899';
    return '#64748b';
  };

  return (
    <div className="knowledge-graph-view" style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header & Controls Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0 0 0.25rem 0', color: 'var(--text-primary, #f8fafc)' }}>
            Knowledge Graph Explorer
          </h1>
          <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-muted, #94a3b8)' }}>
            Evidence-backed relational intelligence foundation. Deterministic traversals bounded to &le; 3 hops.
          </p>
        </div>

        {/* View Mode Toggle */}
        <div style={{ display: 'flex', gap: '0.5rem', background: 'rgba(30, 41, 59, 0.7)', padding: '0.25rem', borderRadius: '8px' }}>
          <button
            onClick={() => setViewMode('graph')}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.85rem',
              background: viewMode === 'graph' ? '#2563eb' : 'transparent',
              color: viewMode === 'graph' ? '#fff' : '#94a3b8',
              transition: 'all 0.2s ease',
            }}
          >
            Visual Graph
          </button>
          <button
            onClick={() => setViewMode('ledger')}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.85rem',
              background: viewMode === 'ledger' ? '#2563eb' : 'transparent',
              color: viewMode === 'ledger' ? '#fff' : '#94a3b8',
              transition: 'all 0.2s ease',
            }}
          >
            Relationship Ledger
          </button>
        </div>
      </div>

      {/* Disclaimers & Provenance Note */}
      <div
        style={{
          background: 'rgba(30, 41, 59, 0.5)',
          borderLeft: '4px solid #3b82f6',
          padding: '0.75rem 1rem',
          borderRadius: '4px',
          marginBottom: '1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.8rem',
          color: '#cbd5e1',
        }}
      >
        <span>
          <strong>Relational Integrity:</strong> All edges require validated source provenance, extractor versioning, and confidence &ge; 0.50. Cross-domain connections represent observational association without claiming causality.
        </span>
        <span style={{ padding: '0.2rem 0.5rem', background: 'rgba(59, 130, 246, 0.2)', borderRadius: '4px', color: '#93c5fd', fontWeight: 600 }}>
          V0.7 Active
        </span>
      </div>

      {viewMode === 'graph' ? (
        <div>
          {/* Graph Controls Toolbar */}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
              background: 'rgba(15, 23, 42, 0.6)',
              padding: '1rem',
              borderRadius: '10px',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              marginBottom: '1rem',
            }}
          >
            {/* Search form */}
            <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '0.5rem', flex: 1, minWidth: '280px', maxWidth: '450px' }}>
              <input
                type="text"
                placeholder="Search entity to explore graph..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  flex: 1,
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  background: 'rgba(30, 41, 59, 0.8)',
                  color: '#fff',
                  fontSize: '0.875rem',
                }}
              />
              <button
                type="submit"
                style={{
                  padding: '0.5rem 1rem',
                  borderRadius: '6px',
                  border: 'none',
                  background: '#2563eb',
                  color: '#fff',
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                }}
              >
                Explore
              </button>
            </form>

            {/* Depth Bound Selector */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 500 }}>
                Traversal Depth:
              </span>
              {[1, 2, 3].map((d) => (
                <button
                  key={d}
                  onClick={() => setDepth(d)}
                  style={{
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    background: depth === d ? '#3b82f6' : 'rgba(30, 41, 59, 0.6)',
                    color: depth === d ? '#fff' : '#cbd5e1',
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontSize: '0.8rem',
                  }}
                >
                  {d} Hop{d > 1 ? 's' : ''}
                </button>
              ))}
              <span style={{ fontSize: '0.75rem', color: '#64748b', marginLeft: '0.25rem' }}>
                (max 3)
              </span>
            </div>

            {/* Quick Entity Selector */}
            {sampleEntities.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Focus:</span>
                <select
                  value={centerEntityId || ''}
                  onChange={(e) => setCenterEntityId(e.target.value)}
                  style={{
                    padding: '0.4rem 0.75rem',
                    borderRadius: '6px',
                    background: 'rgba(30, 41, 59, 0.8)',
                    color: '#fff',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    fontSize: '0.85rem',
                  }}
                >
                  {sampleEntities.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.canonical_name} ({e.entity_type})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {error && (
            <div style={{ padding: '1rem', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', borderRadius: '8px', color: '#fca5a5', marginBottom: '1rem' }}>
              {error}
            </div>
          )}

          {/* Main Visualizer Area */}
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 340px', gap: '1.5rem', alignItems: 'start' }}>
            {/* SVG Graph Canvas */}
            <div
              style={{
                position: 'relative',
                background: '#0b0f19',
                borderRadius: '12px',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                overflow: 'hidden',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
                minHeight: '520px',
              }}
            >
              {loading && (
                <div
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'rgba(11, 15, 25, 0.75)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 10,
                    color: '#93c5fd',
                    fontWeight: 600,
                  }}
                >
                  Traversing Relational Graph (Depth {depth})...
                </div>
              )}

              <svg
                width="100%"
                height="520"
                viewBox="0 0 800 520"
                style={{ display: 'block' }}
              >
                <defs>
                  <marker
                    id="arrow"
                    viewBox="0 0 10 10"
                    refX="22"
                    refY="5"
                    markerWidth="6"
                    markerHeight="6"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748b" />
                  </marker>
                  <marker
                    id="arrow-active"
                    viewBox="0 0 10 10"
                    refX="22"
                    refY="5"
                    markerWidth="6"
                    markerHeight="6"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#38bdf8" />
                  </marker>
                </defs>

                {/* Edges */}
                {graphData?.edges.map((edge) => {
                  const srcPos = nodePositions.get(edge.source_entity_id);
                  const tgtPos = nodePositions.get(edge.target_entity_id);
                  if (!srcPos || !tgtPos) return null;

                  const isSelected = selectedEdge?.id === edge.id;
                  const strokeColor = isSelected ? '#38bdf8' : 'rgba(148, 163, 184, 0.35)';
                  const strokeWidth = isSelected ? 3 : 1.5;

                  const midX = (srcPos.x + tgtPos.x) / 2;
                  const midY = (srcPos.y + tgtPos.y) / 2;

                  return (
                    <g key={edge.id} style={{ cursor: 'pointer' }} onClick={() => { setSelectedEdge(edge); setSelectedNode(null); }}>
                      <line
                        x1={srcPos.x}
                        y1={srcPos.y}
                        x2={tgtPos.x}
                        y2={tgtPos.y}
                        stroke={strokeColor}
                        strokeWidth={strokeWidth}
                        markerEnd={isSelected ? 'url(#arrow-active)' : 'url(#arrow)'}
                      />
                      {/* Edge Label Pill */}
                      <g transform={`translate(${midX}, ${midY})`}>
                        <rect
                          x={-42}
                          y={-9}
                          width="84"
                          height="18"
                          rx="4"
                          fill="rgba(15, 23, 42, 0.9)"
                          stroke={isSelected ? '#38bdf8' : 'rgba(255, 255, 255, 0.15)'}
                          strokeWidth="1"
                        />
                        <text
                          textAnchor="middle"
                          y="3"
                          fill={isSelected ? '#38bdf8' : '#cbd5e1'}
                          fontSize="9"
                          fontWeight="600"
                        >
                          {edge.relationship_type.replace(/_/g, ' ')}
                        </text>
                      </g>
                    </g>
                  );
                })}

                {/* Nodes */}
                {graphData?.nodes.map((node) => {
                  const pos = nodePositions.get(node.id);
                  if (!pos) return null;
                  const isCenter = node.id === graphData.center_node_id;
                  const isSelected = selectedNode?.id === node.id;
                  const nodeColor = getNodeColor(node.entity_type);
                  const radius = isCenter ? 24 : 18;

                  return (
                    <g
                      key={node.id}
                      transform={`translate(${pos.x}, ${pos.y})`}
                      style={{ cursor: 'pointer' }}
                      onClick={() => {
                        setSelectedNode(node);
                        setSelectedEdge(null);
                      }}
                    >
                      {/* Outer selection glow */}
                      {(isCenter || isSelected) && (
                        <circle
                          r={radius + 6}
                          fill="none"
                          stroke={isCenter ? '#60a5fa' : '#38bdf8'}
                          strokeWidth="2"
                          strokeDasharray={isCenter ? '4 2' : 'none'}
                          opacity="0.8"
                        />
                      )}
                      <circle
                        r={radius}
                        fill={nodeColor}
                        stroke="#0f172a"
                        strokeWidth="2.5"
                      />
                      <text
                        textAnchor="middle"
                        y="4"
                        fill="#ffffff"
                        fontSize={isCenter ? '11' : '9'}
                        fontWeight="700"
                      >
                        {(node.label || node.canonical_name || 'UN').slice(0, 2).toUpperCase()}
                      </text>
                      {/* Node Label Below */}
                      <text
                        textAnchor="middle"
                        y={radius + 14}
                        fill={isSelected || isCenter ? '#ffffff' : '#94a3b8'}
                        fontSize="11"
                        fontWeight={isCenter ? '700' : '500'}
                      >
                        {(() => {
                          const name = node.label || node.canonical_name || 'Node';
                          return name.length > 22 ? name.slice(0, 20) + '...' : name;
                        })()}
                      </text>
                    </g>
                  );
                })}
              </svg>

              {/* Graph Stats Overlay */}
              <div
                style={{
                  position: 'absolute',
                  bottom: '10px',
                  left: '12px',
                  fontSize: '0.75rem',
                  color: '#64748b',
                  background: 'rgba(15, 23, 42, 0.8)',
                  padding: '4px 8px',
                  borderRadius: '4px',
                }}
              >
                Nodes: {graphData?.total_nodes || 0} | Edges: {graphData?.total_edges || 0} | Depth: {depth}
              </div>
            </div>

            {/* Inspector Sidebar */}
            <div
              style={{
                background: 'rgba(15, 23, 42, 0.8)',
                borderRadius: '12px',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                padding: '1.25rem',
                minHeight: '520px',
              }}
            >
              {selectedNode ? (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                    <span
                      style={{
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        background: getNodeColor(selectedNode.entity_type),
                        color: '#fff',
                      }}
                    >
                      {selectedNode.entity_type}
                    </span>
                    {selectedNode.country_code && (
                      <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                        [{selectedNode.country_code}]
                      </span>
                    )}
                  </div>

                  <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.25rem', color: '#fff' }}>
                    {selectedNode.label || selectedNode.canonical_name || 'Selected Entity'}
                  </h3>

                  <div style={{ marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <button
                      onClick={() => setCenterEntityId(selectedNode.id)}
                      style={{
                        padding: '0.5rem',
                        borderRadius: '6px',
                        border: 'none',
                        background: '#3b82f6',
                        color: '#fff',
                        fontWeight: 600,
                        cursor: 'pointer',
                        fontSize: '0.85rem',
                      }}
                    >
                      Center Graph Here
                    </button>
                    {onSelectEntity && (
                      <button
                        onClick={() => onSelectEntity(selectedNode.id)}
                        style={{
                          padding: '0.5rem',
                          borderRadius: '6px',
                          border: '1px solid rgba(255, 255, 255, 0.2)',
                          background: 'transparent',
                          color: '#cbd5e1',
                          fontWeight: 600,
                          cursor: 'pointer',
                          fontSize: '0.85rem',
                        }}
                      >
                        View Full Entity Profile &rarr;
                      </button>
                    )}
                  </div>

                  {/* Connected Edges List */}
                  <h4 style={{ fontSize: '0.85rem', color: '#94a3b8', textTransform: 'uppercase', margin: '0 0 0.5rem 0' }}>
                    Incident Connections
                  </h4>
                  <div style={{ maxHeight: '220px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {graphData?.edges
                      .filter(
                        (e) =>
                          e.source_entity_id === selectedNode.id ||
                          e.target_entity_id === selectedNode.id
                      )
                      .map((e) => {
                        const isOut = e.source_entity_id === selectedNode.id;
                        const otherId = isOut ? e.target_entity_id : e.source_entity_id;
                        const otherNode = graphData.nodes.find((n) => n.id === otherId);
                        return (
                          <div
                            key={e.id}
                            onClick={() => { setSelectedEdge(e); setSelectedNode(null); }}
                            style={{
                              padding: '0.5rem',
                              borderRadius: '6px',
                              background: 'rgba(30, 41, 59, 0.6)',
                              cursor: 'pointer',
                              fontSize: '0.8rem',
                              border: '1px solid rgba(255, 255, 255, 0.05)',
                            }}
                          >
                            <span style={{ color: isOut ? '#60a5fa' : '#a78bfa', fontWeight: 600 }}>
                              {isOut ? '&rarr;' : '&larr;'} {e.relationship_type.replace(/_/g, ' ')}
                            </span>
                            <div style={{ color: '#e2e8f0', fontWeight: 500, marginTop: '2px' }}>
                              {otherNode?.label || otherNode?.canonical_name || otherId}
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>
              ) : selectedEdge ? (
                <div>
                  <span
                    style={{
                      padding: '0.2rem 0.5rem',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      background: 'rgba(56, 189, 248, 0.2)',
                      color: '#38bdf8',
                      display: 'inline-block',
                      marginBottom: '0.5rem',
                    }}
                  >
                    {selectedEdge.relationship_type.toUpperCase()}
                  </span>

                  <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.1rem', color: '#fff' }}>
                    Relationship Details
                  </h3>

                  <div style={{ marginBottom: '1rem', fontSize: '0.85rem' }}>
                    <div style={{ color: '#94a3b8', marginBottom: '0.25rem' }}>Confidence Score:</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <div style={{ flex: 1, height: '6px', background: 'rgba(255, 255, 255, 0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                        <div
                          style={{
                            width: `${(selectedEdge.confidence * 100).toFixed(0)}%`,
                            height: '100%',
                            background: '#10b981',
                          }}
                        />
                      </div>
                      <span style={{ fontWeight: 700, color: '#10b981' }}>
                        {(selectedEdge.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <div style={{ color: '#94a3b8', fontSize: '0.8rem', marginBottom: '0.25rem' }}>Provenance / Evidence:</div>
                    <div
                      style={{
                        padding: '0.75rem',
                        background: 'rgba(30, 41, 59, 0.6)',
                        borderRadius: '6px',
                        fontSize: '0.8rem',
                        color: '#cbd5e1',
                        fontStyle: 'italic',
                        lineHeight: 1.4,
                        borderLeft: '3px solid #38bdf8',
                      }}
                    >
                      &ldquo;{selectedEdge.evidence}&rdquo;
                    </div>
                  </div>

                  {selectedEdge.source_document_id && (
                    <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.5rem' }}>
                      Doc ID: {selectedEdge.source_document_id}
                    </div>
                  )}
                  {selectedEdge.source_event_id && (
                    <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      Event ID: {selectedEdge.source_event_id}
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ color: '#64748b', fontSize: '0.875rem', textAlign: 'center', marginTop: '2rem' }}>
                  Click on any node or edge in the graph to inspect verified provenance and ontology attributes.
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Tabular Ledger Mode */
        <div style={{ background: 'rgba(15, 23, 42, 0.6)', borderRadius: '12px', padding: '1.5rem', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
          {/* Filters */}
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', alignItems: 'center' }}>
            <select
              value={ledgerFilterType}
              onChange={(e) => { setLedgerFilterType(e.target.value); setLedgerPage(1); }}
              style={{
                padding: '0.5rem 0.75rem',
                borderRadius: '6px',
                background: 'rgba(30, 41, 59, 0.8)',
                color: '#fff',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                fontSize: '0.85rem',
              }}
            >
              <option value="">All Controlled Relationship Types</option>
              <option value="headquartered_in">headquartered_in</option>
              <option value="operates_in">operates_in</option>
              <option value="member_of">member_of</option>
              <option value="owns">owns</option>
              <option value="produces">produces</option>
              <option value="exports">exports</option>
              <option value="governs">governs</option>
              <option value="allied_with">allied_with</option>
              <option value="leads">leads</option>
            </select>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', color: '#cbd5e1' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', textAlign: 'left', color: '#94a3b8' }}>
                <th style={{ padding: '0.75rem 0.5rem' }}>Source Entity</th>
                <th style={{ padding: '0.75rem 0.5rem' }}>Relationship Type</th>
                <th style={{ padding: '0.75rem 0.5rem' }}>Target Entity</th>
                <th style={{ padding: '0.75rem 0.5rem' }}>Confidence</th>
                <th style={{ padding: '0.75rem 0.5rem' }}>Evidence Snippet</th>
                <th style={{ padding: '0.75rem 0.5rem' }}>Extractor</th>
              </tr>
            </thead>
            <tbody>
              {ledgerData?.items.map((rel) => (
                <tr key={rel.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                  <td style={{ padding: '0.75rem 0.5rem', fontWeight: 600, color: '#fff' }}>
                    {rel.source_entity?.canonical_name || rel.source_entity_id}
                  </td>
                  <td style={{ padding: '0.75rem 0.5rem' }}>
                    <span style={{ padding: '0.15rem 0.4rem', borderRadius: '4px', background: 'rgba(59, 130, 246, 0.2)', color: '#93c5fd', fontWeight: 600, fontSize: '0.75rem' }}>
                      {rel.relationship_type}
                    </span>
                  </td>
                  <td style={{ padding: '0.75rem 0.5rem', fontWeight: 600, color: '#fff' }}>
                    {rel.target_entity?.canonical_name || rel.target_entity_id}
                  </td>
                  <td style={{ padding: '0.75rem 0.5rem', color: '#10b981', fontWeight: 700 }}>
                    {(rel.confidence * 100).toFixed(0)}%
                  </td>
                  <td style={{ padding: '0.75rem 0.5rem', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontStyle: 'italic', color: '#94a3b8' }}>
                    {rel.evidence}
                  </td>
                  <td style={{ padding: '0.75rem 0.5rem', fontSize: '0.75rem', color: '#64748b' }}>
                    {rel.extractor_version}
                  </td>
                </tr>
              ))}
              {ledgerData?.items.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
                    No relationships found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {/* Pagination */}
          {ledgerData && ledgerData.total_pages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
              <button
                disabled={ledgerPage <= 1}
                onClick={() => setLedgerPage((p) => Math.max(1, p - 1))}
                style={{ padding: '0.4rem 0.8rem', borderRadius: '4px', border: '1px solid rgba(255, 255, 255, 0.1)', background: 'transparent', color: '#cbd5e1', cursor: ledgerPage <= 1 ? 'not-allowed' : 'pointer' }}
              >
                Previous
              </button>
              <span style={{ display: 'flex', alignItems: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
                Page {ledgerPage} of {ledgerData.total_pages}
              </span>
              <button
                disabled={ledgerPage >= ledgerData.total_pages}
                onClick={() => setLedgerPage((p) => Math.min(ledgerData.total_pages, p + 1))}
                style={{ padding: '0.4rem 0.8rem', borderRadius: '4px', border: '1px solid rgba(255, 255, 255, 0.1)', background: 'transparent', color: '#cbd5e1', cursor: ledgerPage >= ledgerData.total_pages ? 'not-allowed' : 'pointer' }}
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
