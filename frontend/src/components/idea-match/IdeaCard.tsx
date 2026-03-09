'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Zap, Star } from 'lucide-react';
import {
  IdeaCard as IdeaCardType,
  FRAMEWORK_LABELS,
  FRAMEWORK_DESCRIPTIONS,
  ENGAGEMENT_TYPE_LABELS,
} from '@/types/ideaMatch';

interface IdeaCardProps {
  idea: IdeaCardType;
  rank?: number;
  isBoldBet?: boolean;
}

const ENGAGEMENT_TYPE_COLORS: Record<string, string> = {
  awareness: 'bg-blue-50 text-blue-700 border-blue-200',
  engagement: 'bg-amber-50 text-amber-700 border-amber-200',
  persuasion: 'bg-green-50 text-green-700 border-green-200',
  brand_personality: 'bg-purple-50 text-purple-700 border-purple-200',
};

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-[var(--smoke)] w-32 shrink-0">{label}</span>
      <div className="flex-1 h-1 rounded-full bg-[var(--linen)]">
        <div
          className="h-1 rounded-full bg-[var(--clay)]"
          style={{ width: `${(value / 10) * 100}%` }}
        />
      </div>
      <span className="text-[var(--charcoal)] font-mono text-[11px] w-6 text-right">{value.toFixed(1)}</span>
    </div>
  );
}

export function IdeaCardComponent({ idea, rank, isBoldBet = false }: IdeaCardProps) {
  const [expanded, setExpanded] = useState(false);

  const frameworkLabel = FRAMEWORK_LABELS[idea.framework_used] || idea.framework_used;
  const frameworkDesc = FRAMEWORK_DESCRIPTIONS[idea.framework_used] || '';
  const engagementLabel = ENGAGEMENT_TYPE_LABELS[idea.engagement_type] || idea.engagement_type;
  const engagementColor = ENGAGEMENT_TYPE_COLORS[idea.engagement_type] || 'bg-gray-50 text-gray-600 border-gray-200';

  return (
    <div
      className={`rounded-xl border transition-all duration-200 ${
        isBoldBet
          ? 'border-[var(--clay)]/40 bg-[var(--clay-pale)]/40'
          : 'border-[var(--border)] bg-white'
      } shadow-[var(--shadow-sm)]`}
    >
      {/* Header */}
      <div className="p-5 pb-4">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2.5">
            {isBoldBet ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[var(--clay)] text-white text-[10px] font-medium uppercase tracking-wide">
                <Star className="w-3 h-3" />
                Bold Bet
              </span>
            ) : rank !== undefined && (
              <span className="w-6 h-6 rounded-full bg-[var(--linen)] text-[var(--smoke)] text-xs font-medium flex items-center justify-center shrink-0">
                {rank}
              </span>
            )}
            <h3 className="text-[var(--slate)] font-semibold text-base leading-snug">
              {idea.title}
            </h3>
          </div>
          {idea.score && (
            <div className="flex items-center gap-1 shrink-0">
              <Zap className="w-3.5 h-3.5 text-[var(--clay)]" />
              <span className="text-[var(--clay)] font-semibold text-sm">{idea.score.total.toFixed(1)}</span>
              <span className="text-[var(--mist)] text-xs">/10</span>
            </div>
          )}
        </div>

        {/* Badges row */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {/* Framework badge */}
          <span
            className="px-2 py-0.5 rounded-md border border-[var(--clay)]/30 bg-[var(--clay-pale)] text-[var(--clay-dark)] text-[11px] font-medium"
            title={frameworkDesc}
          >
            {frameworkLabel}
          </span>

          {/* Engagement type */}
          <span className={`px-2 py-0.5 rounded-md border text-[11px] font-medium ${engagementColor}`}>
            {engagementLabel}
          </span>

          {/* Format */}
          <span className="px-2 py-0.5 rounded-md border border-[var(--border)] bg-[var(--parchment)] text-[var(--charcoal)] text-[11px]">
            {idea.format}
          </span>

          {/* Tone */}
          {idea.tone.slice(0, 2).map((t) => (
            <span
              key={t}
              className="px-2 py-0.5 rounded-md border border-[var(--border-light)] bg-[var(--cream)] text-[var(--smoke)] text-[11px]"
            >
              {t}
            </span>
          ))}
        </div>

        {/* Concept preview */}
        <p className="text-[var(--charcoal)] text-sm leading-relaxed">
          {expanded ? idea.concept : idea.concept.slice(0, 180) + (idea.concept.length > 180 ? '…' : '')}
        </p>
      </div>

      {/* Expanded section */}
      {expanded && (
        <div className="px-5 pb-4 border-t border-[var(--border-light)] pt-4 space-y-4">
          {/* Platforms */}
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[var(--mist)] mb-1.5">Platforms</p>
            <div className="flex flex-wrap gap-1.5">
              {idea.platforms.map((p) => (
                <span key={p} className="px-2 py-0.5 rounded-md bg-[var(--linen)] text-[var(--charcoal)] text-xs">
                  {p}
                </span>
              ))}
            </div>
          </div>

          {/* Framework rationale */}
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[var(--mist)] mb-1.5">Why this template</p>
            <p className="text-[var(--smoke)] text-sm leading-relaxed">{idea.framework_rationale}</p>
          </div>

          {/* What to avoid */}
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[var(--mist)] mb-1.5">What to avoid</p>
            <p className="text-[var(--smoke)] text-sm leading-relaxed">{idea.avoid}</p>
          </div>

          {/* Scores */}
          {idea.score && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--mist)] mb-2">Scores</p>
              <div className="space-y-1.5">
                <ScoreBar label="Brand fit" value={idea.score.brand_fit} />
                <ScoreBar label="Strategic relevance" value={idea.score.strategic_relevance} />
                <ScoreBar label="Originality" value={idea.score.originality} />
                <ScoreBar label="Engagement potential" value={idea.score.engagement_potential} />
                <ScoreBar label="Feasibility" value={idea.score.feasibility} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Expand toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-center gap-1.5 py-2.5 border-t border-[var(--border-light)] text-[var(--smoke)] hover:text-[var(--charcoal)] text-xs transition-colors"
      >
        {expanded ? (
          <>
            <ChevronUp className="w-3.5 h-3.5" />
            Less detail
          </>
        ) : (
          <>
            <ChevronDown className="w-3.5 h-3.5" />
            Full concept, template rationale, scores
          </>
        )}
      </button>
    </div>
  );
}
