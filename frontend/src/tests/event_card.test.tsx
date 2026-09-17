import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EventCard } from '../components/EventCard';
import type { EventCluster } from '../types/intelligence';

const baseMockCluster: EventCluster = {
  id: 'c1111111-1111-1111-1111-111111111111',
  canonical_title: 'Federal Reserve Holds Interest Rates Constant',
  canonical_summary: 'The Federal Reserve held policy rates steady at 5.25%-5.50%.',
  event_type: 'central_bank_decision',
  event_time: '2026-05-15T18:00:00Z',
  location: 'Washington',
  confidence: 0.94,
  importance: 0.88,
  status: 'active',
  first_event_time: '2026-05-15T18:00:00Z',
  last_event_time: '2026-05-15T18:25:00Z',
  member_count: 3,
  unique_source_count: 2,
  metadata_: {
    entities: ['Federal Reserve', 'Jerome Powell'],
  },
  created_at: '2026-05-15T18:30:00Z',
  updated_at: '2026-05-15T18:30:00Z',
};

describe('EventCard Component', () => {
  it('renders complete event metadata and badges accurately', () => {
    const handleClick = vi.fn();
    render(<EventCard cluster={baseMockCluster} onClick={handleClick} />);

    expect(screen.getByText('Federal Reserve Holds Interest Rates Constant')).toBeDefined();
    expect(screen.getByText('Washington')).toBeDefined();
    expect(screen.getByText('IMP: 0.88')).toBeDefined();
    expect(screen.getByText('CONF: 0.94')).toBeDefined();
    expect(screen.getByText('3 reports from 2 sources')).toBeDefined();
    expect(screen.getByText('Federal Reserve')).toBeDefined();
    expect(screen.getByText('Jerome Powell')).toBeDefined();

    // Trigger click
    fireEvent.click(screen.getByText('Federal Reserve Holds Interest Rates Constant'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('renders "Time unavailable" when event_time is null (never fabricates current time)', () => {
    const clusterWithoutTime: EventCluster = {
      ...baseMockCluster,
      event_time: null,
    };
    render(<EventCard cluster={clusterWithoutTime} />);
    expect(screen.getByText('Time unavailable')).toBeDefined();
  });

  it('renders "Location unavailable" when location is null (never fabricates location)', () => {
    const clusterWithoutLoc: EventCluster = {
      ...baseMockCluster,
      location: null,
    };
    render(<EventCard cluster={clusterWithoutLoc} />);
    expect(screen.getByText('Location unavailable')).toBeDefined();
  });
});
