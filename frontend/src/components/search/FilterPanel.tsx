'use client';

import { FilterConfig } from '@/types/search';
import { RotateCcw } from 'lucide-react';

interface FilterPanelProps {
  filters: FilterConfig;
  onChange: (filters: FilterConfig) => void;
}

interface FilterSliderProps {
  label: string;
  value: number | undefined;
  min: number;
  max: number;
  step: number;
  defaultValue: number;
  unit?: string;
  formatValue?: (value: number | undefined) => string;
  onChange: (value: number | undefined) => void;
  optional?: boolean;
}

function FilterSlider({
  label,
  value,
  min,
  max,
  step,
  defaultValue,
  unit = '%',
  formatValue,
  onChange,
  optional = false,
}: FilterSliderProps) {
  const displayValue = formatValue
    ? formatValue(value)
    : value !== undefined
    ? `${value}${unit}`
    : 'Cualquiera';

  const percentage = value !== undefined
    ? ((value - min) / (max - min)) * 100
    : 0;

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <label className="text-sm text-light-secondary font-medium">
          {label}
          {optional && <span className="text-light-tertiary/70 ml-1 text-xs font-normal">(opcional)</span>}
        </label>
        <span className="text-sm font-mono font-medium text-ember-warm tabular-nums">
          {displayValue}
        </span>
      </div>

      <div className="relative">
        {/* Track */}
        <div className="h-1 bg-dark-ash rounded-full overflow-hidden">
          <div
            className="h-full bg-ember-warm rounded-full transition-all duration-150"
            style={{ width: `${percentage}%` }}
          />
        </div>

        {/* Invisible range input overlay */}
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value ?? defaultValue}
          onChange={(e) => {
            const newValue = parseFloat(e.target.value);
            if (optional && newValue === defaultValue) {
              onChange(undefined);
            } else {
              onChange(newValue);
            }
          }}
          className="absolute inset-0 w-full h-1 opacity-0 cursor-pointer"
          style={{ '--value': `${percentage}%` } as React.CSSProperties}
        />

        {/* Custom thumb */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-[14px] h-[14px] bg-ember-warm rounded-full
                     border-2 border-dark-secondary shadow-sm pointer-events-none transition-all duration-150"
          style={{ left: `calc(${percentage}% - 7px)` }}
        />
      </div>

      <div className="flex justify-between text-[11px] text-light-tertiary/60 font-mono">
        <span>{optional ? 'Cualquiera' : `${min}${unit}`}</span>
        <span>{max}{unit}{max === 100 ? '' : '+'}</span>
      </div>
    </div>
  );
}

const AGE_BRACKETS = ['13-17', '18-24', '25-34', '35-44', '45-54', '55+'];

export function FilterPanel({ filters, onChange }: FilterPanelProps) {
  const handleChange = <K extends keyof FilterConfig>(key: K, value: FilterConfig[K]) => {
    onChange({ ...filters, [key]: value });
  };

  const handleReset = () => {
    onChange({
      min_credibility_score: 70,
      min_spain_audience_pct: 60,
    });
  };

  const toggleAgeRange = (range: string) => {
    const current = filters.target_age_ranges ?? [];
    const updated = current.includes(range)
      ? current.filter((r) => r !== range)
      : [...current, range];
    handleChange('target_age_ranges', updated.length ? updated : undefined);
  };

  const hasChanges =
    filters.min_credibility_score !== 70 ||
    filters.min_spain_audience_pct !== 60 ||
    filters.min_engagement_rate !== undefined ||
    filters.min_follower_growth_rate !== undefined ||
    filters.target_audience_gender !== undefined ||
    (filters.target_age_ranges && filters.target_age_ranges.length > 0);

  return (
    <div className="bg-dark-secondary rounded-xl border border-dark-border/60 p-6 max-w-3xl mx-auto shadow-card">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xs font-semibold text-light-tertiary uppercase tracking-[0.10em]">
          Filtros de búsqueda
        </h3>
        {hasChanges && (
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 text-xs text-light-tertiary hover:text-ember-warm transition-colors"
          >
            <RotateCcw className="w-3 h-3" />
            Restablecer
          </button>
        )}
      </div>

      {/* Filter grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <FilterSlider
          label="Credibilidad Mín."
          value={filters.min_credibility_score}
          min={0} max={100} step={5} defaultValue={70}
          onChange={(value) => handleChange('min_credibility_score', value ?? 70)}
        />

        <FilterSlider
          label="Audiencia España Mín."
          value={filters.min_spain_audience_pct}
          min={0} max={100} step={5} defaultValue={60}
          onChange={(value) => handleChange('min_spain_audience_pct', value ?? 60)}
        />

        <FilterSlider
          label="Engagement Mín."
          value={filters.min_engagement_rate}
          min={0} max={15} step={0.5} defaultValue={0}
          onChange={(value) => handleChange('min_engagement_rate', value)}
          optional
          formatValue={(v) => (v !== undefined ? `${v}%` : 'Cualquiera')}
        />

        <FilterSlider
          label="Crecimiento 6M Mín."
          value={filters.min_follower_growth_rate}
          min={-20} max={50} step={5} defaultValue={-20}
          onChange={(value) =>
            handleChange('min_follower_growth_rate', value === -20 ? undefined : value)
          }
          optional
          formatValue={(v) => (v !== undefined ? `${v > 0 ? '+' : ''}${v}%` : 'Cualquiera')}
        />

        {/* Gender */}
        <div className="space-y-2.5">
          <label className="text-sm text-light-secondary font-medium">
            Género de Audiencia Objetivo
          </label>
          <div className="flex gap-1.5">
            {(['any', 'female', 'male'] as const).map((gender) => (
              <button
                key={gender}
                onClick={() =>
                  handleChange('target_audience_gender', gender === 'any' ? undefined : gender)
                }
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all border ${
                  (filters.target_audience_gender === gender) ||
                  (gender === 'any' && !filters.target_audience_gender)
                    ? 'bg-ember-warm/10 text-ember-warm border-ember-warm/30'
                    : 'bg-dark-tertiary text-light-secondary border-dark-border/60 hover:text-light-primary hover:border-dark-border'
                }`}
              >
                {gender === 'any' ? 'Cualquiera' : gender === 'female' ? 'Mujeres' : 'Hombres'}
              </button>
            ))}
          </div>
          {filters.target_audience_gender && (
            <FilterSlider
              label={`Mín. % ${filters.target_audience_gender === 'female' ? 'Mujeres' : 'Hombres'}`}
              value={filters.min_target_gender_pct ?? 50}
              min={50} max={90} step={5} defaultValue={50}
              onChange={(value) => handleChange('min_target_gender_pct', value)}
            />
          )}
        </div>

        {/* Age brackets */}
        <div className="space-y-2.5 sm:col-span-2">
          <label className="text-sm text-light-secondary font-medium">
            Rangos de Edad Objetivo
          </label>
          <div className="flex flex-wrap gap-1.5">
            {AGE_BRACKETS.map((range) => (
              <button
                key={range}
                onClick={() => toggleAgeRange(range)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all border ${
                  filters.target_age_ranges?.includes(range)
                    ? 'bg-ember-warm/10 text-ember-warm border-ember-warm/30'
                    : 'bg-dark-tertiary text-light-secondary border-dark-border/60 hover:text-light-primary hover:border-dark-border'
                }`}
              >
                {range}
              </button>
            ))}
          </div>
          {filters.target_age_ranges && filters.target_age_ranges.length > 0 && (
            <FilterSlider
              label="Mín. % Edad Combinada"
              value={filters.min_target_age_pct ?? 30}
              min={20} max={80} step={5} defaultValue={30}
              onChange={(value) => handleChange('min_target_age_pct', value)}
            />
          )}
        </div>
      </div>

      {/* Active filters summary */}
      <div className="mt-6 pt-4 border-t border-dark-border/40">
        <div className="flex flex-wrap gap-1.5 items-center">
          <span className="text-[11px] text-light-tertiary/60">Activos:</span>
          <FilterBadge label={`Credibilidad ≥ ${filters.min_credibility_score}%`} />
          <FilterBadge label={`España ≥ ${filters.min_spain_audience_pct}%`} />
          {filters.min_engagement_rate !== undefined && (
            <FilterBadge label={`Engagement ≥ ${filters.min_engagement_rate}%`} />
          )}
          {filters.min_follower_growth_rate !== undefined && (
            <FilterBadge label={`Crecimiento ≥ ${filters.min_follower_growth_rate > 0 ? '+' : ''}${filters.min_follower_growth_rate}%`} />
          )}
          {filters.target_audience_gender && (
            <FilterBadge label={`Audiencia ${filters.target_audience_gender === 'female' ? 'femenina' : 'masculina'} ≥ ${filters.min_target_gender_pct ?? 50}%`} />
          )}
          {filters.target_age_ranges && filters.target_age_ranges.length > 0 && (
            <FilterBadge label={`Edades: ${filters.target_age_ranges.join(', ')}`} />
          )}
        </div>
      </div>
    </div>
  );
}

function FilterBadge({ label }: { label: string }) {
  return (
    <span className="px-2 py-0.5 rounded text-[11px] bg-ember-warm/[0.08] text-ember-warm border border-ember-warm/[0.18]">
      {label}
    </span>
  );
}
