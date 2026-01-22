'use client';

import { ScoreComponents } from '@/types/search';
import { cn } from '@/lib/utils';

interface ScoreBreakdownProps {
  scores: ScoreComponents;
}

const SCORE_CONFIG: Record<keyof ScoreComponents, {
  label: string;
  description: string;
  color: string;
  bgColor: string;
}> = {
  credibility: {
    label: 'Credibility',
    description: 'Audience authenticity',
    color: 'bg-[#6366f1]',
    bgColor: 'bg-[#6366f1]/20',
  },
  engagement: {
    label: 'Engagement',
    description: 'Interaction rate',
    color: 'bg-metric-excellent',
    bgColor: 'bg-metric-excellent/20',
  },
  audience_match: {
    label: 'Audience Match',
    description: 'Demographics fit',
    color: 'bg-accent-gold',
    bgColor: 'bg-accent-gold/20',
  },
  growth: {
    label: 'Growth',
    description: '6-month trend',
    color: 'bg-[#ec4899]',
    bgColor: 'bg-[#ec4899]/20',
  },
  geography: {
    label: 'Geography',
    description: 'Spain audience %',
    color: 'bg-[#14b8a6]',
    bgColor: 'bg-[#14b8a6]/20',
  },
  brand_affinity: {
    label: 'Brand Affinity',
    description: 'Audience overlap with target brand',
    color: 'bg-[#f97316]',
    bgColor: 'bg-[#f97316]/20',
  },
  creative_fit: {
    label: 'Creative Fit',
    description: 'Alignment with campaign concept',
    color: 'bg-[#8b5cf6]',
    bgColor: 'bg-[#8b5cf6]/20',
  },
  niche_match: {
    label: 'Niche Match',
    description: 'Content category alignment',
    color: 'bg-[#06b6d4]',
    bgColor: 'bg-[#06b6d4]/20',
  },
};

const WEIGHT_LABELS: Record<keyof ScoreComponents, string> = {
  credibility: '15%',
  engagement: '20%',
  audience_match: '15%',
  growth: '5%',
  geography: '10%',
  brand_affinity: '15%',
  creative_fit: '15%',
  niche_match: '5%',
};

export function ScoreBreakdown({ scores }: ScoreBreakdownProps) {
  const scoreEntries = Object.entries(scores) as [keyof ScoreComponents, number][];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-light-primary uppercase tracking-wider">
          Score Breakdown
        </h4>
        <span className="text-xs text-light-tertiary">
          weighted scoring
        </span>
      </div>

      {/* Score Bars */}
      <div className="space-y-3">
        {scoreEntries.map(([key, value]) => {
          const config = SCORE_CONFIG[key];
          const percentage = value * 100;
          const weight = WEIGHT_LABELS[key];

          return (
            <div key={key} className="group">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-light-secondary group-hover:text-light-primary transition-colors">
                    {config.label}
                  </span>
                  <span className="text-[10px] text-light-tertiary px-1.5 py-0.5 rounded bg-dark-tertiary">
                    {weight}
                  </span>
                </div>
                <span className="font-mono font-medium text-sm text-light-primary">
                  {percentage.toFixed(0)}%
                </span>
              </div>

              {/* Progress Bar */}
              <div className="relative h-2 bg-dark-tertiary rounded-full overflow-hidden">
                <div
                  className={cn(
                    'absolute inset-y-0 left-0 rounded-full transition-all duration-700 ease-out',
                    config.color
                  )}
                  style={{ width: `${percentage}%` }}
                />
                {/* Glow effect */}
                <div
                  className={cn(
                    'absolute inset-y-0 left-0 rounded-full blur-sm opacity-50 transition-all duration-700 ease-out',
                    config.color
                  )}
                  style={{ width: `${percentage}%` }}
                />
              </div>

              {/* Description on hover */}
              <p className="text-[10px] text-light-tertiary mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {config.description}
              </p>
            </div>
          );
        })}
      </div>

      {/* Summary */}
      <div className="pt-3 border-t border-dark-border/50">
        <div className="flex flex-col gap-1">
          <span className="text-xs text-light-tertiary">
            Default weights: Engagement 20% · Credibility 15% · Audience 15% · Brand Affinity 15% · Creative Fit 15%
          </span>
          <span className="text-xs text-light-tertiary">
            Geography 10% · Growth 5% · Niche 5%
          </span>
        </div>
      </div>
    </div>
  );
}
