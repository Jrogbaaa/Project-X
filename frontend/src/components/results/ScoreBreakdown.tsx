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
  glowColor: string;
}> = {
  credibility: {
    label: 'Credibilidad',
    description: 'Autenticidad de la audiencia',
    color: 'bg-[#6366f1]',
    bgColor: 'bg-[#6366f1]/15',
    glowColor: 'shadow-[#6366f1]/30',
  },
  engagement: {
    label: 'Engagement',
    description: 'Tasa de interacción',
    color: 'bg-metric-excellent',
    bgColor: 'bg-metric-excellent/15',
    glowColor: 'shadow-metric-excellent/30',
  },
  audience_match: {
    label: 'Match Audiencia',
    description: 'Ajuste demográfico',
    color: 'bg-ember-core',
    bgColor: 'bg-ember-core/15',
    glowColor: 'shadow-ember-core/30',
  },
  growth: {
    label: 'Crecimiento',
    description: 'Tendencia 6 meses',
    color: 'bg-[#ec4899]',
    bgColor: 'bg-[#ec4899]/15',
    glowColor: 'shadow-[#ec4899]/30',
  },
  geography: {
    label: 'Geografía',
    description: '% audiencia en España',
    color: 'bg-ice-soft',
    bgColor: 'bg-ice-soft/15',
    glowColor: 'shadow-ice-soft/30',
  },
  brand_affinity: {
    label: 'Afinidad Marca',
    description: 'Overlap audiencia con marca objetivo',
    color: 'bg-ember-hot',
    bgColor: 'bg-ember-hot/15',
    glowColor: 'shadow-ember-hot/30',
  },
  creative_fit: {
    label: 'Encaje Creativo',
    description: 'Alineación con concepto de campaña',
    color: 'bg-[#8b5cf6]',
    bgColor: 'bg-[#8b5cf6]/15',
    glowColor: 'shadow-[#8b5cf6]/30',
  },
  niche_match: {
    label: 'Match Nicho',
    description: 'Alineación de nicho de contenido',
    color: 'bg-ice-bright',
    bgColor: 'bg-ice-bright/15',
    glowColor: 'shadow-ice-bright/30',
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
        <h4 className="text-sm font-semibold text-ember-glow/80 uppercase tracking-wider">
          Desglose de Puntuación
        </h4>
        <span className="text-xs text-light-tertiary">
          puntuación ponderada
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
                  <span className="text-[10px] text-light-tertiary px-1.5 py-0.5 rounded bg-dark-ash">
                    {weight}
                  </span>
                </div>
                <span className="font-mono font-medium text-sm text-light-primary">
                  {percentage.toFixed(0)}%
                </span>
              </div>

              {/* Progress Bar */}
              <div className="relative h-2 bg-dark-ash rounded-full overflow-hidden">
                <div
                  className={cn(
                    'absolute inset-y-0 left-0 rounded-full transition-all duration-700 ease-out shadow-sm',
                    config.color,
                    config.glowColor
                  )}
                  style={{ width: `${percentage}%` }}
                />
                {/* Glow effect at fill point */}
                <div
                  className={cn(
                    'absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full blur-md opacity-60 transition-all duration-700 ease-out',
                    config.color
                  )}
                  style={{ left: `calc(${percentage}% - 6px)` }}
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
      <div className="pt-3 border-t border-dark-border/30">
        <div className="flex flex-col gap-1">
          <span className="text-xs text-light-tertiary">
            Pesos por defecto: Engagement 20% · Credibilidad 15% · Audiencia 15% · Afinidad Marca 15% · Encaje Creativo 15%
          </span>
          <span className="text-xs text-light-tertiary">
            Geografía 10% · Crecimiento 5% · Nicho 5%
          </span>
        </div>
      </div>
    </div>
  );
}
