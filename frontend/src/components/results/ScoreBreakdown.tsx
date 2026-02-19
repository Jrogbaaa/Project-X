'use client';

import { ScoreComponents } from '@/types/search';
import { cn } from '@/lib/utils';

interface ScoreBreakdownProps {
  scores: ScoreComponents;
}

const SCORE_CONFIG: Record<keyof ScoreComponents, {
  label: string;
  description: string;
  barColor: string;
}> = {
  credibility: {
    label: 'Credibilidad',
    description: 'Autenticidad de la audiencia',
    barColor: 'bg-[#5B6CF6]',
  },
  engagement: {
    label: 'Engagement',
    description: 'Tasa de interacción',
    barColor: 'bg-metric-excellent',
  },
  audience_match: {
    label: 'Match Audiencia',
    description: 'Ajuste demográfico',
    barColor: 'bg-ember-warm',
  },
  growth: {
    label: 'Crecimiento',
    description: 'Tendencia 6 meses',
    barColor: 'bg-[#D95F8F]',
  },
  geography: {
    label: 'Geografía',
    description: '% audiencia en España',
    barColor: 'bg-ice-bright',
  },
  brand_affinity: {
    label: 'Afinidad Marca',
    description: 'Overlap audiencia con marca',
    barColor: 'bg-ember-hot',
  },
  creative_fit: {
    label: 'Encaje Creativo',
    description: 'Alineación con concepto de campaña',
    barColor: 'bg-[#8B60F0]',
  },
  niche_match: {
    label: 'Match Nicho',
    description: 'Alineación de nicho de contenido',
    barColor: 'bg-ice-soft',
  },
};

const WEIGHT_LABELS: Record<keyof ScoreComponents, string> = {
  credibility:    '15%',
  engagement:     '20%',
  audience_match: '15%',
  growth:         '5%',
  geography:      '10%',
  brand_affinity: '15%',
  creative_fit:   '15%',
  niche_match:    '5%',
};

export function ScoreBreakdown({ scores }: ScoreBreakdownProps) {
  const scoreEntries = Object.entries(scores) as [keyof ScoreComponents, number][];

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
        {scoreEntries.map(([key, value]) => {
          const config = SCORE_CONFIG[key];
          const percentage = value * 100;
          const weight = WEIGHT_LABELS[key];

          return (
            <div key={key} className="group/bar">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-light-secondary group-hover/bar:text-light-primary transition-colors">
                    {config.label}
                  </span>
                  <span className="text-[9px] text-light-tertiary/50 font-mono">{weight}</span>
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
          Engagement 20% · Credibilidad 15% · Audiencia 15% · Afinidad 15% · Creativo 15% · Geografía 10% · Crecimiento 5% · Nicho 5%
        </p>
      </div>
    </div>
  );
}
