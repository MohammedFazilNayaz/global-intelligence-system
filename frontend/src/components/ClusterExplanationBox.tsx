import React from 'react';
import type { EventClusterMember } from '../types/intelligence';

interface ClusterExplanationBoxProps {
  members: EventClusterMember[];
}

export const ClusterExplanationBox: React.FC<ClusterExplanationBoxProps> = ({ members }) => {
  if (!members || members.length <= 1) {
    return (
      <div className="section-box">
        <div className="section-title">Clustering Rationale</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          Single report event. This cluster was initialized from the primary document evidence below.
        </p>
      </div>
    );
  }

  // Find representative member and non-representative members to inspect pairwise match metrics
  const representative = members.find((m) => m.is_representative) || members[0];
  const groupedMembers = members.filter((m) => m.id !== representative.id);

  return (
    <div className="section-box">
      <div className="section-title">
        <span>Clustering Evidence — Why Reports Are Grouped</span>
        <span style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
          {members.length} Source Reports Co-Referenced
        </span>
      </div>

      <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
        The clustering engine verified that multiple incoming reports refer to the same real-world event
        based on multi-dimensional semantic compatibility:
      </p>

      {groupedMembers.map((member) => {
        const scores = member.metadata_?.scores;
        const hasScores = !!scores;
        const eventTypeScore = scores?.event_type_score;
        const temporalScore = scores?.temporal_score;
        const locationScore = scores?.location_score;
        const actorScore = scores?.actor_overlap_score;
        const entityScore = scores?.entity_overlap_score;
        const lexicalScore = scores?.lexical_score;
        const finalScore = scores?.final_score ?? member.membership_score;
        const threshold = scores?.threshold ?? 0.75;
        const timeDiff = scores?.time_diff_minutes;
        const method = typeof member.membership_method === 'string'
          ? member.membership_method
          : typeof scores?.method === 'string'
          ? scores.method
          : 'deterministic_v0.3';

        // Human-readable translations (only when scores actually exist)
        const eventTypeExplanation = eventTypeScore !== undefined
          ? (eventTypeScore === 1.0 ? 'Identical Event Type' : 'Compatible Event Category')
          : 'Type score not recorded';

        const locationExplanation = locationScore !== undefined
          ? (locationScore === 1.0
            ? 'Same Geographic Location'
            : locationScore === 0.8
            ? 'Compatible / Regional Match'
            : 'Location Unknown / Neutral')
          : 'Location score not recorded';

        let temporalExplanation = 'Time score not recorded';
        if (temporalScore !== undefined) {
          if (timeDiff !== undefined) {
            if (timeDiff === 0) temporalExplanation = 'Exact Same Timestamp';
            else if (timeDiff < 60) temporalExplanation = `${timeDiff} min difference`;
            else if (timeDiff < 1440) temporalExplanation = `${Math.round(timeDiff / 60)} hour difference`;
            else temporalExplanation = `${Math.round(timeDiff / 1440)} day difference`;
          } else {
            temporalExplanation = 'Within temporal threshold window';
          }
        }

        const actorExplanation = actorScore !== undefined
          ? (actorScore >= 0.8 ? 'Strong Actor Overlap' : actorScore > 0 ? 'Partial Actor Overlap' : 'No Overlap Recorded')
          : 'Actor score not recorded';

        const entityExplanation = entityScore !== undefined
          ? (entityScore >= 0.8 ? 'High Entity Overlap' : entityScore > 0 ? 'Partial Entity Overlap' : 'No Overlap Recorded')
          : 'Entity score not recorded';

        const lexicalExplanation = lexicalScore !== undefined
          ? (lexicalScore >= 0.7 ? 'Strong Headline/Summary Overlap' : lexicalScore > 0 ? 'Partial Text Overlap' : 'Low Text Overlap')
          : 'Lexical score not recorded';

        return (
          <div
            key={member.id}
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '1rem',
              marginBottom: '0.75rem',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '0.6rem',
                borderBottom: '1px solid var(--border-subtle)',
                paddingBottom: '0.4rem',
                flexWrap: 'wrap',
                gap: '0.5rem',
              }}
            >
              <div>
                <strong style={{ color: 'var(--text-primary)', fontSize: '0.85rem' }}>
                  Grouped Document: "{member.document?.title || 'Untitled Report'}"
                </strong>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginLeft: '0.5rem' }}>
                  via {member.document?.source_name || 'Source'}
                </span>
                <span style={{ color: 'var(--accent-indigo)', fontSize: '0.7rem', marginLeft: '0.5rem', fontFamily: 'var(--font-mono)' }}>
                  [{method}]
                </span>
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Match: </span>
                <strong style={{ color: 'var(--accent-cyan)' }}>{(finalScore * 100).toFixed(1)}%</strong>
                {hasScores && (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}> (min {(threshold * 100).toFixed(0)}%)</span>
                )}
              </div>
            </div>

            <div className="explanation-breakdown">
              <div className="explanation-card">
                <div className="explanation-card-label">Event Type Match</div>
                <div className="explanation-card-value">
                  {eventTypeScore !== undefined ? `${(eventTypeScore * 100).toFixed(0)}%` : 'N/A'}
                </div>
                <div className="explanation-card-desc">{eventTypeExplanation}</div>
              </div>

              <div className="explanation-card">
                <div className="explanation-card-label">Temporal Proximity</div>
                <div className="explanation-card-value">
                  {temporalScore !== undefined ? `${(temporalScore * 100).toFixed(0)}%` : 'N/A'}
                </div>
                <div className="explanation-card-desc">{temporalExplanation}</div>
              </div>

              <div className="explanation-card">
                <div className="explanation-card-label">Location Match</div>
                <div className="explanation-card-value">
                  {locationScore !== undefined ? `${(locationScore * 100).toFixed(0)}%` : 'N/A'}
                </div>
                <div className="explanation-card-desc">{locationExplanation}</div>
              </div>

              <div className="explanation-card">
                <div className="explanation-card-label">Actor Overlap</div>
                <div className="explanation-card-value">
                  {actorScore !== undefined ? `${(actorScore * 100).toFixed(0)}%` : 'N/A'}
                </div>
                <div className="explanation-card-desc">{actorExplanation}</div>
              </div>

              <div className="explanation-card">
                <div className="explanation-card-label">Entity Overlap</div>
                <div className="explanation-card-value">
                  {entityScore !== undefined ? `${(entityScore * 100).toFixed(0)}%` : 'N/A'}
                </div>
                <div className="explanation-card-desc">{entityExplanation}</div>
              </div>

              <div className="explanation-card">
                <div className="explanation-card-label">Lexical Similarity</div>
                <div className="explanation-card-value">
                  {lexicalScore !== undefined ? `${(lexicalScore * 100).toFixed(0)}%` : 'N/A'}
                </div>
                <div className="explanation-card-desc">{lexicalExplanation}</div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
