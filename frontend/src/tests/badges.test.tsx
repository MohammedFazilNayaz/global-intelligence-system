import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ImportanceBadge, ConfidenceBadge, EventTypeBadge } from '../components/Badges';

describe('Badges Component Suite', () => {
  it('strictly distinguishes Importance from Confidence', () => {
    const { container: impContainer } = render(<ImportanceBadge importance={0.85} />);
    const { container: confContainer } = render(<ConfidenceBadge confidence={0.92} />);

    expect(screen.getByText('IMP: 0.85')).toBeDefined();
    expect(screen.getByText('CONF: 0.92')).toBeDefined();

    // Check distinct CSS classes
    const impEl = impContainer.querySelector('.badge-imp-high');
    const confEl = confContainer.querySelector('.badge-conf-high');
    expect(impEl).not.toBeNull();
    expect(confEl).not.toBeNull();
  });

  it('handles missing importance gracefully without fabricating values', () => {
    render(<ImportanceBadge importance={null} />);
    expect(screen.getByText('IMP: UNSET')).toBeDefined();
  });

  it('handles missing confidence gracefully without fabricating values', () => {
    render(<ConfidenceBadge confidence={null} />);
    expect(screen.getByText('CONF: UNSET')).toBeDefined();
  });

  it('correctly maps severity thresholds for importance', () => {
    const { container: high } = render(<ImportanceBadge importance={0.90} />);
    expect(high.querySelector('.badge-imp-high')).not.toBeNull();

    const { container: med } = render(<ImportanceBadge importance={0.50} />);
    expect(med.querySelector('.badge-imp-med')).not.toBeNull();

    const { container: low } = render(<ImportanceBadge importance={0.20} />);
    expect(low.querySelector('.badge-imp-low')).not.toBeNull();
  });

  it('renders formatted event type badge', () => {
    render(<EventTypeBadge eventType="central_bank_decision" />);
    expect(screen.getByText('central bank decision')).toBeDefined();
  });
});
