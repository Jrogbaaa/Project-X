'use client';

import { ScoreComponents } from '@/types/search';
import { cn } from '@/lib/utils';

interface ScoreBreakdownProps {
  scores: ScoreComponents;
}

const VISIBLE_KEYS: (keyof ScoreComponents)[] = [
  'niche_match',
  'creative_fit',
  'engagement',
  'brand_affinity',
];

const SCORE_CONFIG: Partial<Record<keyof ScoreComponents, {
  label: string;
  description: string;
  barColor: string;
  weight: string;
}>> = {
  niche_match: {
    label: 'Match Nicho',
    description: 'Alineación de nicho de contenido',
    barColor: 'bg-ice-soft',
    weight: '50%',
  },
  creative_fit: {
    label: 'Encaje Creativo',
    description: 'Alineación con concepto de campaña',
    barColor: 'bg-[#8B60F0]',
    weight: '30%',
  },
  engagement: {
    label: 'Engagement',
    description: 'Tasa de interacción',
    barColor: 'bg-metric-excellent',
    weight: '10%',
  },
  brand_affinity: {
    label: 'Afinidad Marca',
    description: 'Overlap audiencia con marca',
    barColor: 'bg-ember-hot',
    weight: '10%',
  },
};

export function ScoreBreakdown({ scores }: ScoreBreakdownProps) {
  return (
    <div className="space-y-3.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h4 className="text-[10px] font-semibold text-ember-warm/70 uppercase tracking-[0.10em]">
          Desglose de Puntuación
        </h4>
        <span className="text-[10px] text-light-tertiary/50">ponderada</span>
      </div>

      {/* Score bars */}
      <div className="space-y-2.5">
        {VISIBLE_KEYS.map((key) => {
          const config = SCORE_CONFIG[key];
          if (!config) return null;
          const percentage = scores[key] * 100;

          return (
            <div key={key} className="group/bar">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-light-secondary group-hover/bar:text-light-primary transition-colors">
                    {config.label}
                  </span>
                  <span className="text-[9px] text-light-tertiary/50 font-mono">{config.weight}</span>
                </div>
                <span className="font-mono text-xs font-medium text-light-primary tabular-nums">
                  {percentage.toFixed(0)}%
                </span>
              </div>

              {/* Thin progress bar */}
              <div className="h-[3px] bg-dark-ash rounded-full overflow-hidden">
                <div
                  className={cn('h-full rounded-full transition-all duration-600 ease-out', config.barColor)}
                  style={{ width: `${percentage}%` }}
                />
              </div>

              {/* Description on hover */}
              <p className="text-[10px] text-light-tertiary/50 mt-0.5 opacity-0 group-hover/bar:opacity-100 transition-opacity">
                {config.description}
              </p>
            </div>
          );
        })}
      </div>

      {/* Weight legend */}
      <div className="pt-2.5 border-t border-dark-border/30">
        <p className="text-[10px] text-light-tertiary/45 leading-relaxed">
          Nicho 50% · Creativo 30% · Engagement 10% · Afinidad 10%
        </p>
      </div>
    </div>
  );
}
