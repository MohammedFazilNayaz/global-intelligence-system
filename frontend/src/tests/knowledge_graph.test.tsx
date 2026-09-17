import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { KnowledgeGraphView } from '../views/KnowledgeGraphView';
import { api } from '../api/client';
import type { KnowledgeGraphResponse, PaginatedRelationships } from '../types/intelligence';

vi.mock('../api/client', () => ({
  api: {
    getEntities: vi.fn(),
    getEntityGraph: vi.fn(),
    getRelationships: vi.fn(),
    searchGraph: vi.fn(),
  },
}));

describe('KnowledgeGraphView Integration Suite (V0.7)', () => {
  const mockGraphData: KnowledgeGraphResponse = {
    center_node_id: 'ent-1',
    depth: 1,
    nodes: [
      {
        id: 'ent-1',
        canonical_name: 'Federal Reserve',
        entity_type: 'CENTRAL_BANK',
        country_code: 'US',
      },
      {
        id: 'ent-2',
        canonical_name: 'US Dollar',
        entity_type: 'CURRENCY',
      },
      {
        id: 'ent-3',
        canonical_name: 'United States',
        entity_type: 'COUNTRY',
        country_code: 'US',
      },
    ],
    edges: [
      {
        id: 'edge-1',
        source_entity_id: 'ent-1',
        target_entity_id: 'ent-2',
        relationship_type: 'governs',
        confidence: 0.95,
        evidence: 'Federal Reserve governs monetary policy for the US Dollar.',
      },
      {
        id: 'edge-2',
        source_entity_id: 'ent-1',
        target_entity_id: 'ent-3',
        relationship_type: 'operates_in',
        confidence: 0.92,
        evidence: 'Federal Reserve operates in United States.',
      },
    ],
    total_nodes: 3,
    total_edges: 2,
  };

  const mockLedgerData: PaginatedRelationships = {
    items: [
      {
        id: 'rel-1',
        source_entity_id: 'ent-1',
        target_entity_id: 'ent-2',
        relationship_type: 'governs',
        confidence: 0.95,
        evidence: 'Federal Reserve governs monetary policy for the US Dollar.',
        extraction_method: 'deterministic_rules_v0.7',
        extractor_version: 'v0.7.0',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        source_entity: {
          id: 'ent-1',
          canonical_name: 'Federal Reserve',
          normalized_name: 'federal reserve',
          entity_type: 'CENTRAL_BANK',
          country_code: 'US',
          description: null,
          created_at: '',
          updated_at: '',
        },
        target_entity: {
          id: 'ent-2',
          canonical_name: 'US Dollar',
          normalized_name: 'us dollar',
          entity_type: 'CURRENCY',
          country_code: null,
          description: null,
          created_at: '',
          updated_at: '',
        },
      },
    ],
    total: 1,
    page: 1,
    page_size: 15,
    total_pages: 1,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getEntities as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        {
          id: 'ent-1',
          canonical_name: 'Federal Reserve',
          normalized_name: 'federal reserve',
          entity_type: 'CENTRAL_BANK',
          country_code: 'US',
          description: null,
          created_at: '',
          updated_at: '',
        },
      ],
      total: 1,
      limit: 10,
      offset: 0,
    });
    (api.getEntityGraph as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockGraphData);
    (api.getRelationships as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockLedgerData);
  });

  it('renders KnowledgeGraphView header, relational integrity notice, and depth bounds', async () => {
    render(<KnowledgeGraphView initialEntityId="ent-1" />);

    expect(screen.getByText('Knowledge Graph Explorer')).toBeDefined();
    expect(screen.getByText(/Relational Integrity:/)).toBeDefined();
    expect(screen.getByText(/1 Hop/)).toBeDefined();
    expect(screen.getByText(/2 Hops/)).toBeDefined();
    expect(screen.getByText(/3 Hops/)).toBeDefined();

    await waitFor(() => {
      expect(api.getEntityGraph).toHaveBeenCalledWith('ent-1', 1, 3, 50);
      expect(screen.getAllByText(/Federal Reserve/).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('displays node selection details in inspector sidebar', async () => {
    render(<KnowledgeGraphView initialEntityId="ent-1" />);

    await waitFor(() => {
      expect(screen.getAllByText(/Federal Reserve/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/CENTRAL_BANK/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Center Graph Here')).toBeDefined();
      expect(screen.getAllByText(/governs/).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('switches to Relationship Ledger mode and renders evidence-backed rows', async () => {
    render(<KnowledgeGraphView initialEntityId="ent-1" />);

    const ledgerTabBtn = screen.getByText('Relationship Ledger');
    fireEvent.click(ledgerTabBtn);

    await waitFor(() => {
      expect(api.getRelationships).toHaveBeenCalled();
      expect(screen.getByText('Federal Reserve governs monetary policy for the US Dollar.')).toBeDefined();
      expect(screen.getByText('95%')).toBeDefined();
      expect(screen.getByText('v0.7.0')).toBeDefined();
    });
  });

  it('changes traversal depth and queries bounded graph', async () => {
    render(<KnowledgeGraphView initialEntityId="ent-1" />);

    await waitFor(() => {
      expect(api.getEntityGraph).toHaveBeenCalledWith('ent-1', 1, 3, 50);
    });

    const depth2Btn = screen.getByText('2 Hops');
    fireEvent.click(depth2Btn);

    await waitFor(() => {
      expect(api.getEntityGraph).toHaveBeenCalledWith('ent-1', 2, 3, 50);
    });
  });
});
