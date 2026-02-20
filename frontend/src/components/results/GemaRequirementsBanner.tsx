'use client';

import { ShieldCheck } from 'lucide-react';
import { FilterConfig, RankedInfluencer } from '@/types/search';

export interface GemaRequirementsBannerProps {
  filters: FilterConfig;
  results: RankedInfluencer[];
}

function computeGenderSummary(filters: FilterConfig, results: RankedInfluencer[]): string {
  if (filters.target_audience_gender && filters.min_target_gender_pct) {
    const label = filters.target_audience_gender === 'female' ? 'mujeres' : 'hombres';
    return `Mínimo ${filters.min_target_gender_pct}% ${label}`;
  }

  const validResults = results.filter(
    (r) => r.raw_data.audience_genders && Object.keys(r.raw_data.audience_genders).length > 0
  );
  if (validResults.length === 0) return 'Datos no disponibles';

  let totalFemale = 0;
  let totalMale = 0;
  for (const r of validResults) {
    const g = r.raw_data.audience_genders;
    totalFemale += g['female'] ?? g['Female'] ?? 0;
    totalMale += g['male'] ?? g['Male'] ?? 0;
  }
  const avgFemale = Math.round(totalFemale / validResults.length);
  const avgMale = Math.round(totalMale / validResults.length);
  return `~${avgFemale}% mujeres / ~${avgMale}% hombres`;
}

function computeAgeSummary(filters: FilterConfig, results: RankedInfluencer[]): string {
  if (filters.target_age_ranges && filters.target_age_ranges.length > 0) {
    const rangesLabel = filters.target_age_ranges.join(', ');
    const minPct = filters.min_target_age_pct ? ` (≥${filters.min_target_age_pct}%)` : '';
    return `${rangesLabel}${minPct}`;
  }

  const validResults = results.filter(
    (r) =>
      r.raw_data.audience_age_distribution &&
      Object.keys(r.raw_data.audience_age_distribution).length > 0
  );
  if (validResults.length === 0) return 'Datos no disponibles';

  const accumulator: Record<string, { total: number; count: number }> = {};
  for (const r of validResults) {
    for (const [band, pct] of Object.entries(r.raw_data.audience_age_distribution)) {
      if (!accumulator[band]) accumulator[band] = { total: 0, count: 0 };
      accumulator[band].total += pct;
      accumulator[band].count += 1;
    }
  }

  const sorted = Object.entries(accumulator)
    .map(([band, { total, count }]) => ({ band, avg: Math.round(total / count) }))
    .sort((a, b) => {
      const aStart = parseInt(a.band.split('-')[0]) || 0;
      const bStart = parseInt(b.band.split('-')[0]) || 0;
      return bStart - aStart === 0 ? b.avg - a.avg : b.avg - a.avg;
    })
    .slice(0, 2);

  return sorted.map((e) => `${e.band} (~${e.avg}%)`).join(' · ');
}

export function GemaRequirementsBanner({ filters, results }: GemaRequirementsBannerProps) {
  const engagementDisplay = filters.min_engagement_rate
    ? `≥ ${filters.min_engagement_rate.toFixed(1)}%`
    : (() => {
        const valid = results.filter((r) => r.raw_data.engagement_rate != null);
        if (valid.length === 0) return 'N/A';
        const avg =
          valid.reduce((s, r) => s + (r.raw_data.engagement_rate ?? 0), 0) / valid.length;
        return `~${avg.toFixed(1)}% (media)`;
      })();

  const requirements = [
    {
      label: 'Audiencia española',
      value: `≥ ${filters.min_spain_audience_pct}%`,
    },
    {
      label: 'Distribución de género',
      value: computeGenderSummary(filters, results),
    },
    {
      label: 'Distribución de edad',
      value: computeAgeSummary(filters, results),
    },
    {
      label: 'Credibilidad (solo IG)',
      value: `≥ ${filters.min_credibility_score}%`,
    },
    {
      label: 'Tasa de engagement (ER)',
      value: engagementDisplay,
    },
  ];

  return (
    <div className="rounded-xl border border-ice-bright/20 bg-ice-bright/[0.04] px-5 py-4">
      <div className="flex items-center gap-2 mb-3.5">
        <ShieldCheck className="w-3.5 h-3.5 text-ice-bright flex-shrink-0" />
        <p className="text-xs font-medium text-light-secondary">
          Todos estos influencers cumplen los siguientes requisitos GEMA:
        </p>
      </div>

      <div className="flex flex-wrap gap-2.5">
        {requirements.map((req) => (
          <div
            key={req.label}
            className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-dark-secondary border border-dark-border/50 shadow-card min-w-[140px] flex-1"
          >
            <span className="text-metric-excellent text-sm leading-none mt-0.5 flex-shrink-0">
              ✓
            </span>
            <div className="min-w-0">
              <p className="text-[10px] text-light-tertiary/70 uppercase tracking-wider font-mono leading-none mb-1">
                {req.label}
              </p>
              <p className="text-xs font-semibold text-light-primary font-mono tabular-nums">
                {req.value}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
