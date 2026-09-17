import React, { useState } from 'react';
import type { EventIntelligenceDossier, EvidenceClass } from '../types/intelligence';

interface EventDossierCardProps {
  dossier: EventIntelligenceDossier;
  onSelectRelatedEvent?: (eventId: string) => void;
  className?: string;
}

export const EventDossierCard: React.FC<EventDossierCardProps> = ({
  dossier,
  onSelectRelatedEvent,
  className = '',
}) => {
  const [expandedSection, setExpandedSection] = useState<'all' | 'compact'>('compact');

  const renderEvidenceBadge = (cls: EvidenceClass) => {
    switch (cls) {
      case 'OBSERVED':
        return (
          <span className="px-1.5 py-0.5 text-[10px] font-mono tracking-wider uppercase font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 rounded">
            OBSERVED
          </span>
        );
      case 'DIRECT':
        return (
          <span className="px-1.5 py-0.5 text-[10px] font-mono tracking-wider uppercase font-semibold bg-blue-950/80 text-blue-300 border border-blue-500/40 rounded">
            DIRECT
          </span>
        );
      case 'HISTORICAL_ASSOCIATION':
        return (
          <span className="px-1.5 py-0.5 text-[10px] font-mono tracking-wider uppercase font-semibold bg-cyan-950/80 text-cyan-300 border border-cyan-500/40 rounded">
            HISTORICAL
          </span>
        );
      case 'ANALYTICAL_IMPLICATION':
        return (
          <span className="px-1.5 py-0.5 text-[10px] font-mono tracking-wider uppercase font-semibold bg-purple-950/80 text-purple-300 border border-purple-500/40 rounded">
            ANALYTICAL INFERENCE
          </span>
        );
      case 'UNKNOWN':
      default:
        return (
          <span className="px-1.5 py-0.5 text-[10px] font-mono tracking-wider uppercase font-semibold bg-neutral-800 text-neutral-400 border border-neutral-600 rounded">
            UNCONFIRMED
          </span>
        );
    }
  };

  const formatTimestamp = (ts?: string | null) => {
    if (!ts) return 'N/A';
    try {
      const d = new Date(ts);
      return d.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
    } catch {
      return ts;
    }
  };

  const formatAge = (ts?: string | null) => {
    if (!ts) return 'Unknown';
    try {
      const diffMs = Date.now() - new Date(ts).getTime();
      const mins = Math.floor(diffMs / 60000);
      if (mins < 60) return `${mins}m ago`;
      const hrs = Math.floor(mins / 60);
      if (hrs < 24) return `${hrs}h ago`;
      const days = Math.floor(hrs / 24);
      return `${days}d ago`;
    } catch {
      return 'N/A';
    }
  };

  const gradeColor =
    dossier.why_it_matters.importance_grade === 'CRITICAL'
      ? 'bg-rose-500/20 text-rose-300 border-rose-500/50'
      : dossier.why_it_matters.importance_grade === 'HIGH'
      ? 'bg-amber-500/20 text-amber-300 border-amber-500/50'
      : 'bg-blue-500/20 text-blue-300 border-blue-500/50';

  return (
    <div
      className={`bg-slate-900/90 border border-slate-700/80 rounded-xl shadow-2xl p-5 text-slate-100 backdrop-blur-md transition-all ${className}`}
      id={`dossier-${dossier.what_happened.event_id}`}
    >
      {/* Top Banner: 20-30 Second Scannable Header */}
      <div className="border-b border-slate-800 pb-4 mb-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-mono font-bold uppercase tracking-wider rounded border bg-slate-800 text-cyan-400 border-cyan-500/30">
              INTELLIGENCE DOSSIER
            </span>
            <span className={`px-2 py-0.5 text-xs font-mono font-bold uppercase tracking-wider rounded border ${gradeColor}`}>
              {dossier.why_it_matters.importance_grade} ({dossier.why_it_matters.importance_score})
            </span>
            <span className="text-xs text-slate-400 font-mono">
              CONFIDENCE: {(dossier.confidence * 100).toFixed(0)}%
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
            <span>PUB: {formatAge(dossier.publication_time)}</span>
            <button
              onClick={() => setExpandedSection(s => (s === 'compact' ? 'all' : 'compact'))}
              className="text-xs px-2.5 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded text-slate-300 transition-colors"
            >
              {expandedSection === 'compact' ? 'Expand All Fields (21)' : 'Compact View'}
            </button>
          </div>
        </div>

        {/* 1. WHAT HAPPENED */}
        <h2 className="text-lg md:text-xl font-bold text-white tracking-tight leading-snug">
          {dossier.what_happened.title}
        </h2>
        {dossier.what_happened.summary && (
          <p className="mt-1.5 text-sm text-slate-300 leading-relaxed font-sans">
            {dossier.what_happened.summary}
          </p>
        )}

        {/* 2. WHY IT MATTERS */}
        <div className="mt-3 p-3 bg-slate-950/60 border-l-2 border-cyan-500 rounded-r-md">
          <div className="text-[11px] font-mono uppercase tracking-wider text-cyan-400 font-semibold mb-1">
            WHY IT MATTERS / SIGNIFICANCE
          </div>
          <p className="text-xs text-slate-200 leading-relaxed font-sans">
            {dossier.why_it_matters.significance_summary}
          </p>
        </div>
      </div>

      {/* Actors & Impacts Matrix (Scannable Grid) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        {/* Involved vs Affected */}
        <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2 flex items-center justify-between">
            <span>3. DIRECTLY INVOLVED</span>
            <span className="text-[11px] text-slate-500">{dossier.directly_involved.length}</span>
          </div>
          {dossier.directly_involved.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {dossier.directly_involved.map((ent, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-1.5 bg-slate-800/80 border border-slate-700 px-2 py-1 rounded text-xs"
                >
                  <span className="font-medium text-slate-200">{ent.name}</span>
                  {ent.role && <span className="text-[10px] text-slate-400">({ent.role})</span>}
                  {renderEvidenceBadge(ent.evidence_class)}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">No direct primary actor specified in reporting.</p>
          )}

          <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mt-3 mb-2 flex items-center justify-between">
            <span>4. DIRECTLY AFFECTED</span>
            <span className="text-[11px] text-slate-500">{dossier.directly_affected.length}</span>
          </div>
          {dossier.directly_affected.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {dossier.directly_affected.map((ent, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-1.5 bg-slate-800/80 border border-slate-700 px-2 py-1 rounded text-xs"
                >
                  <span className="font-medium text-rose-200">{ent.name}</span>
                  {ent.role && <span className="text-[10px] text-slate-400">({ent.role})</span>}
                  {renderEvidenceBadge(ent.evidence_class)}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">No direct target entity specified.</p>
          )}
        </div>

        {/* Beneficiaries vs Exposures (Phase F Neutral Phrasing) */}
        <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs font-mono uppercase tracking-wider text-emerald-400 mb-2 flex items-center justify-between">
            <span>5. POTENTIAL BENEFICIARIES</span>
            <span className="text-[11px] text-slate-500">{dossier.potential_beneficiaries.length}</span>
          </div>
          {dossier.potential_beneficiaries.length > 0 ? (
            <div className="space-y-1.5">
              {dossier.potential_beneficiaries.slice(0, 3).map((item, idx) => (
                <div key={idx} className="text-xs bg-slate-900/90 border border-slate-800 p-1.5 rounded">
                  <div className="flex items-center justify-between gap-1 mb-0.5">
                    <span className="font-semibold text-emerald-300">{item.name}</span>
                    {renderEvidenceBadge(item.evidence_class)}
                  </div>
                  <div className="text-[11px] text-slate-300">{item.rationale}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">Insufficient evidence of direct structural upside.</p>
          )}

          <div className="text-xs font-mono uppercase tracking-wider text-amber-400 mt-3 mb-2 flex items-center justify-between">
            <span>6. POTENTIAL EXPOSURES</span>
            <span className="text-[11px] text-slate-500">{dossier.potential_exposures.length}</span>
          </div>
          {dossier.potential_exposures.length > 0 ? (
            <div className="space-y-1.5">
              {dossier.potential_exposures.slice(0, 3).map((item, idx) => (
                <div key={idx} className="text-xs bg-slate-900/90 border border-slate-800 p-1.5 rounded">
                  <div className="flex items-center justify-between gap-1 mb-0.5">
                    <span className="font-semibold text-amber-300">{item.name}</span>
                    {renderEvidenceBadge(item.evidence_class)}
                  </div>
                  <div className="text-[11px] text-slate-300">{item.rationale}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">No secondary downside exposures identified.</p>
          )}
        </div>
      </div>

      {/* Geographies & Sectors Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        {/* Countries */}
        <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
            7. AFFECTED COUNTRIES ({dossier.affected_countries.length})
          </div>
          {dossier.affected_countries.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {dossier.affected_countries.map((c, idx) => (
                <span
                  key={idx}
                  className="px-2 py-0.5 bg-slate-800 border border-slate-700 text-xs rounded text-slate-200"
                >
                  <strong className="text-cyan-300">{c.country_code}</strong> - {c.country_name}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">Unresolved sovereign nexus.</p>
          )}
        </div>

        {/* Companies */}
        <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
            8. AFFECTED COMPANIES ({dossier.affected_companies.length})
          </div>
          {dossier.affected_companies.length > 0 ? (
            <div className="space-y-1">
              {dossier.affected_companies.slice(0, 3).map((comp, idx) => (
                <div key={idx} className="text-xs text-slate-200">
                  <span className="font-semibold">{comp.name}</span>
                  {comp.sector && <span className="text-slate-400 text-[11px]"> ({comp.sector})</span>}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">No corporate entities explicitly named.</p>
          )}
        </div>

        {/* Sectors */}
        <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
            9. AFFECTED SECTORS ({dossier.affected_sectors.length})
          </div>
          {dossier.affected_sectors.length > 0 ? (
            <div className="space-y-1">
              {dossier.affected_sectors.map((sec, idx) => (
                <div key={idx} className="text-xs bg-slate-900/60 p-1.5 rounded border border-slate-800">
                  <div className="font-semibold text-slate-200">{sec.sector_name}</div>
                  {sec.rationale && <div className="text-[11px] text-slate-400">{sec.rationale}</div>}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">No specific industrial sectors isolated.</p>
          )}
        </div>
      </div>

      {/* Market & Macro Connections (10-14, 18) */}
      <div className="bg-slate-950/50 border border-slate-800 rounded-lg p-3 mb-4">
        <div className="text-xs font-mono uppercase tracking-wider text-cyan-400 mb-2 flex items-center justify-between">
          <span>MARKET & ECONOMIC CONNECTIONS (COMMODITY, FX, EQUITY, RATES)</span>
          <span className="text-[10px] text-slate-400">TEMPORAL CO-MOVEMENT OBSERVED</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {/* Commodity */}
          <div className="bg-slate-900/90 p-2 rounded border border-slate-800">
            <div className="text-[10px] font-mono text-slate-400 uppercase">10. COMMODITY</div>
            {dossier.commodity_connections.length > 0 ? (
              <div className="mt-1 space-y-1">
                {dossier.commodity_connections.slice(0, 2).map((m, idx) => (
                  <div key={idx} className="text-xs">
                    <span className="font-mono font-bold text-amber-300">{m.asset_symbol}</span>
                    {m.return_percent !== null && m.return_percent !== undefined && (
                      <span
                        className={`ml-1 font-mono ${
                          m.return_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {m.return_percent >= 0 ? '+' : ''}
                        {m.return_percent}%
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-500 mt-1">None tracked</div>
            )}
          </div>

          {/* Currency */}
          <div className="bg-slate-900/90 p-2 rounded border border-slate-800">
            <div className="text-[10px] font-mono text-slate-400 uppercase">11. CURRENCY / FX</div>
            {dossier.currency_connections.length > 0 ? (
              <div className="mt-1 space-y-1">
                {dossier.currency_connections.slice(0, 2).map((m, idx) => (
                  <div key={idx} className="text-xs">
                    <span className="font-mono font-bold text-cyan-300">{m.asset_symbol}</span>
                    {m.return_percent !== null && m.return_percent !== undefined && (
                      <span
                        className={`ml-1 font-mono ${
                          m.return_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {m.return_percent >= 0 ? '+' : ''}
                        {m.return_percent}%
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-500 mt-1">None tracked</div>
            )}
          </div>

          {/* Equity */}
          <div className="bg-slate-900/90 p-2 rounded border border-slate-800">
            <div className="text-[10px] font-mono text-slate-400 uppercase">12. EQUITY BENCHMARK</div>
            {dossier.equity_connections.length > 0 ? (
              <div className="mt-1 space-y-1">
                {dossier.equity_connections.slice(0, 2).map((m, idx) => (
                  <div key={idx} className="text-xs">
                    <span className="font-mono font-bold text-violet-300">{m.asset_symbol}</span>
                    {m.return_percent !== null && m.return_percent !== undefined && (
                      <span
                        className={`ml-1 font-mono ${
                          m.return_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {m.return_percent >= 0 ? '+' : ''}
                        {m.return_percent}%
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-500 mt-1">None tracked</div>
            )}
          </div>

          {/* Rates */}
          <div className="bg-slate-900/90 p-2 rounded border border-slate-800">
            <div className="text-[10px] font-mono text-slate-400 uppercase">13. RATES & YIELDS</div>
            {dossier.rate_connections.length > 0 ? (
              <div className="mt-1 space-y-1">
                {dossier.rate_connections.slice(0, 2).map((m, idx) => (
                  <div key={idx} className="text-xs">
                    <span className="font-mono font-bold text-blue-300">{m.asset_symbol}</span>
                    {m.return_percent !== null && m.return_percent !== undefined && (
                      <span className="ml-1 font-mono text-slate-300">{m.return_percent}%</span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-500 mt-1">None tracked</div>
            )}
          </div>
        </div>

        {/* 14. Economic Indicators */}
        {dossier.economic_indicators.length > 0 && (
          <div className="mt-3 pt-2 border-t border-slate-800/80">
            <div className="text-[10px] font-mono text-slate-400 uppercase mb-1">
              14. ECONOMIC INDICATORS
            </div>
            <div className="flex flex-wrap gap-2">
              {dossier.economic_indicators.map((ind, idx) => (
                <div
                  key={idx}
                  className="bg-slate-900 px-2 py-1 rounded border border-slate-800 text-xs flex items-center gap-1.5"
                >
                  <span className="text-slate-300">{ind.indicator_name}:</span>
                  <span className="font-mono font-bold text-cyan-300">
                    {ind.reported_value} {ind.reported_unit}
                  </span>
                  {ind.direction && (
                    <span className="text-[10px] uppercase font-mono text-slate-400">
                      ({ind.direction})
                    </span>
                  )}
                  {renderEvidenceBadge(ind.evidence_class)}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Geopolitical Connections & Related Events (15 & 16) */}
      {(dossier.geopolitical_connections.length > 0 || dossier.related_events.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
          {/* Geopolitical */}
          <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/80">
            <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
              15. GEOPOLITICAL CONNECTIONS ({dossier.geopolitical_connections.length})
            </div>
            {dossier.geopolitical_connections.length > 0 ? (
              <div className="space-y-1.5">
                {dossier.geopolitical_connections.slice(0, 4).map((rel, idx) => (
                  <div
                    key={idx}
                    className="text-xs bg-slate-900/90 border border-slate-800 px-2 py-1.5 rounded flex items-center justify-between gap-1"
                  >
                    <div>
                      <strong className="text-slate-200">{rel.source_entity}</strong>
                      <span className="mx-1 text-cyan-400 font-mono text-[10px]">
                        [{rel.relationship_type}]
                      </span>
                      <strong className="text-slate-200">{rel.target_entity}</strong>
                    </div>
                    {renderEvidenceBadge(rel.evidence_class)}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No formal treaties or bilateral records active.</p>
            )}
          </div>

          {/* Related Events */}
          <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/80">
            <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
              16. RELATED EVENTS ({dossier.related_events.length})
            </div>
            {dossier.related_events.length > 0 ? (
              <div className="space-y-1.5">
                {dossier.related_events.slice(0, 3).map((ev, idx) => (
                  <div
                    key={idx}
                    onClick={() => onSelectRelatedEvent && onSelectRelatedEvent(ev.event_id)}
                    className="text-xs bg-slate-900/90 border border-slate-800 hover:border-slate-600 px-2 py-1.5 rounded cursor-pointer transition-colors"
                  >
                    <div className="font-medium text-cyan-300 hover:underline line-clamp-1">{ev.title}</div>
                    <div className="text-[10px] text-slate-400 font-mono flex items-center justify-between mt-0.5">
                      <span>{ev.event_type}</span>
                      <span>{formatTimestamp(ev.event_time)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">Isolated atomic event; no sibling cluster reports.</p>
            )}
          </div>
        </div>
      )}

      {/* Provenance & Independent Timestamp Bar (Phase I Integrity) */}
      <div className="pt-3 border-t border-slate-800 text-xs font-mono text-slate-400 bg-slate-950/40 -mx-5 -mb-5 p-4 rounded-b-xl">
        <div className="text-[11px] font-semibold uppercase text-slate-300 tracking-wider mb-2 flex items-center justify-between">
          <span>19. SOURCE PROVENANCE & TIMESTAMP INTEGRITY (PHASE I)</span>
          <span className="text-[10px] text-emerald-400 font-mono">NON-FABRICATED TRACE</span>
        </div>

        {/* Source info */}
        {dossier.source_evidence.length > 0 && (
          <div className="mb-2">
            {dossier.source_evidence.map((src, idx) => (
              <div key={idx} className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-semibold text-slate-200">{src.source_name}</span>
                {src.source_domain && <span className="text-slate-400">({src.source_domain})</span>}
                <a
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-cyan-400 hover:underline truncate max-w-xs"
                >
                  {src.url}
                </a>
                {src.content_hash && (
                  <span className="text-[10px] text-slate-500">
                    HASH: {src.content_hash.substring(0, 10)}...
                  </span>
                )}
                {renderEvidenceBadge(src.evidence_class)}
              </div>
            ))}
          </div>
        )}

        {/* Independent Timestamps */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-800/60 text-[11px]">
          <div>
            <span className="text-slate-500 block">PUBLICATION:</span>
            <span className="text-slate-300">{formatTimestamp(dossier.publication_time)}</span>
          </div>
          <div>
            <span className="text-slate-500 block">INGESTION:</span>
            <span className="text-slate-300">{formatTimestamp(dossier.ingestion_time)}</span>
          </div>
          <div>
            <span className="text-slate-500 block">EXTRACTION:</span>
            <span className="text-slate-300">{formatTimestamp(dossier.extraction_time)}</span>
          </div>
          <div>
            <span className="text-slate-500 block">DOSSIER SYNTHESIS:</span>
            <span className="text-slate-300">{formatTimestamp(dossier.last_updated)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
