import React from 'react';

interface ImportanceBadgeProps {
  importance: number | null | undefined;
}

/**
 * IMPORTANCE answers: "How significant is this event?"
 * Range [0.0, 1.0]
 */
export const ImportanceBadge: React.FC<ImportanceBadgeProps> = ({ importance }) => {
  if (importance === null || importance === undefined) {
    return (
      <span className="badge badge-imp-low" title="Importance score unavailable">
        IMP: UNSET
      </span>
    );
  }

  const score = Math.round(importance * 100) / 100;
  let badgeClass = 'badge-imp-low';
  let tier = 'LOW';

  if (score >= 0.75) {
    badgeClass = 'badge-imp-high';
    tier = 'HIGH';
  } else if (score >= 0.4) {
    badgeClass = 'badge-imp-med';
    tier = 'MED';
  }

  return (
    <span
      className={`badge ${badgeClass}`}
      title={`Event Significance: ${score.toFixed(2)} (${tier}) - Real-world impact score`}
    >
      IMP: {score.toFixed(2)}
    </span>
  );
};

interface ConfidenceBadgeProps {
  confidence: number | null | undefined;
}

/**
 * CONFIDENCE answers: "How confident is the system that the extracted representation is correct?"
 * Range [0.0, 1.0]
 */
export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ confidence }) => {
  if (confidence === null || confidence === undefined) {
    return (
      <span className="badge badge-conf-low" title="Confidence score unavailable">
        CONF: UNSET
      </span>
    );
  }

  const score = Math.round(confidence * 100) / 100;
  let badgeClass = 'badge-conf-low';
  let tier = 'LOW';

  if (score >= 0.8) {
    badgeClass = 'badge-conf-high';
    tier = 'HIGH';
  } else if (score >= 0.5) {
    badgeClass = 'badge-conf-med';
    tier = 'MED';
  }

  return (
    <span
      className={`badge ${badgeClass}`}
      title={`Extraction Certainty: ${score.toFixed(2)} (${tier}) - Algorithmic certainty`}
    >
      CONF: {score.toFixed(2)}
    </span>
  );
};

interface EventTypeBadgeProps {
  eventType: string;
}

export const EventTypeBadge: React.FC<EventTypeBadgeProps> = ({ eventType }) => {
  const formatted = eventType.replace(/_/g, ' ');
  return <span className="badge badge-event-type">{formatted}</span>;
};
