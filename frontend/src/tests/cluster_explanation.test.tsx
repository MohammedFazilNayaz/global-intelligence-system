import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ClusterExplanationBox } from '../components/ClusterExplanationBox';
import type { EventClusterMember } from '../types/intelligence';

const mockMembers: EventClusterMember[] = [
  {
    id: 'm1',
    cluster_id: 'c1',
    extracted_event_id: 'e1',
    document_id: 'd1',
    membership_score: 1.0,
    membership_method: 'exact_seed',
    is_representative: true,
    metadata_: {},
    extracted_event: {
      id: 'e1',
      event_type: 'central_bank_decision',
      title: 'Fed Rate Unchanged',
      description: 'Fed holds rates',
      event_time: '2026-05-15T18:00:00Z',
      location: 'Washington',
      confidence_score: 0.95,
      importance_score: 0.85,
      extractor_version: 'v0.2.1',
      entities: ['Federal Reserve'],
    },
    document: {
      id: 'd1',
      source_id: 's1',
      source_name: 'Reuters',
      title: 'Fed leaves rates steady at 5.25%-5.50%',
      url: 'https://reuters.com/rates',
      published_at: '2026-05-15T18:05:00Z',
    },
  },
  {
    id: 'm2',
    cluster_id: 'c1',
    extracted_event_id: 'e2',
    document_id: 'd2',
    membership_score: 0.91,
    membership_method: 'pairwise_match',
    is_representative: false,
    metadata_: {
      scores: {
        event_type_score: 1.0,
        temporal_score: 0.98,
        location_score: 1.0,
        actor_overlap_score: 0.85,
        entity_overlap_score: 0.90,
        lexical_score: 0.76,
        final_score: 0.91,
        threshold: 0.75,
        time_diff_minutes: 18,
      },
      clustering_version: 'v0.3.0',
    },
    extracted_event: {
      id: 'e2',
      event_type: 'central_bank_decision',
      title: 'Federal Reserve Policy Decision',
      description: 'Fed leaves rate target intact',
      event_time: '2026-05-15T18:18:00Z',
      location: 'Washington',
      confidence_score: 0.92,
      importance_score: 0.85,
      extractor_version: 'v0.2.1',
      entities: ['Federal Reserve', 'Jerome Powell'],
    },
    document: {
      id: 'd2',
      source_id: 's2',
      source_name: 'Bloomberg',
      title: 'Fed Keeps Rates Unchanged in Pause',
      url: 'https://bloomberg.com/fed',
      published_at: '2026-05-15T18:20:00Z',
    },
  },
];

describe('ClusterExplanationBox Component', () => {
  it('translates technical grouping metadata into human-readable analyst explanations', () => {
    render(<ClusterExplanationBox members={mockMembers} />);

    expect(screen.getByText(/Clustering Evidence — Why Reports Are Grouped/)).toBeDefined();
    expect(screen.getByText(/Identical Event Type/)).toBeDefined();
    expect(screen.getByText(/Same Geographic Location/)).toBeDefined();
    expect(screen.getByText(/18 min difference/)).toBeDefined();
    expect(screen.getByText(/Strong Actor Overlap/)).toBeDefined();
    expect(screen.getByText(/91.0%/)).toBeDefined();
  });

  it('renders single-member notification when no multi-report grouping exists', () => {
    render(<ClusterExplanationBox members={[mockMembers[0]]} />);

    expect(screen.getByText(/Single report event/)).toBeDefined();
  });
});
