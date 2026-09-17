import React from 'react';
import type { EventCluster } from '../types/intelligence';
import { ImportanceBadge, ConfidenceBadge, EventTypeBadge } from './Badges';

interface EventCardProps {
  cluster: EventCluster;
  onClick?: () => void;
}

export const EventCard: React.FC<EventCardProps> = ({ cluster, onClick }) => {
  // Respect data integrity invariants: never fabricate missing data
  const formattedTime = cluster.event_time
    ? new Date(cluster.event_time).toUTCString().replace('GMT', 'UTC')
    : 'Time unavailable';

  const formattedLocation = cluster.location || 'Location unavailable';

  // Extract entities from metadata_ if available
  const entitiesList: string[] = Array.isArray(cluster.metadata_?.entities)
    ? (cluster.metadata_.entities as string[])
    : [];

  return (
    <div
      className="event-card"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick?.();
        }
      }}
    >
      <div className="event-card-header">
        <h3 className="event-card-title">{cluster.canonical_title}</h3>
        <div className="event-card-badges">
          <EventTypeBadge eventType={cluster.event_type} />
          <ImportanceBadge importance={cluster.importance} />
          <ConfidenceBadge confidence={cluster.confidence} />
        </div>
      </div>

      <div className="event-card-meta">
        <span className="meta-item">
          <span style={{ color: 'var(--text-muted)' }}>When:</span>
          <span className="meta-item-mono">{formattedTime}</span>
        </span>

        <span className="meta-item">
          <span style={{ color: 'var(--text-muted)' }}>Where:</span>
          <span>{formattedLocation}</span>
        </span>

        <span className="meta-item">
          <span style={{ color: 'var(--text-muted)' }}>Evidence:</span>
          <span className="meta-item-mono">
            {cluster.member_count} {cluster.member_count === 1 ? 'report' : 'reports'} from{' '}
            {cluster.unique_source_count} {cluster.unique_source_count === 1 ? 'source' : 'sources'}
          </span>
        </span>
      </div>

      {entitiesList.length > 0 && (
        <div className="event-entities-list">
          {entitiesList.slice(0, 8).map((entity, i) => (
            <span key={i} className="entity-pill">
              {entity}
            </span>
          ))}
          {entitiesList.length > 8 && (
            <span className="entity-pill" style={{ color: 'var(--text-muted)' }}>
              +{entitiesList.length - 8} more
            </span>
          )}
        </div>
      )}
    </div>
  );
};
