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
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-light-secondary">
          {label}
          {optional && <span className="text-light-tertiary ml-1">(opcional)</span>}
        </label>
        <span className="text-sm font-mono font-medium text-accent-gold">
          {displayValue}
        </span>
      </div>
      <div className="relative">
        {/* Track Background */}
        <div className="h-1.5 bg-dark-tertiary rounded-full overflow-hidden">
          {/* Filled Track */}
          <div
            className="h-full bg-gradient-to-r from-accent-gold-dark to-accent-gold rounded-full transition-all duration-200"
            style={{ width: `${percentage}%` }}
          />
        </div>
        {/* Range Input */}
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
          className="absolute inset-0 w-full h-1.5 opacity-0 cursor-pointer"
          style={
            {
              '--value': `${percentage}%`,
            } as React.CSSProperties
          }
        />
        {/* Custom Thumb */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-accent-gold rounded-full shadow-lg shadow-accent-gold/30 border-2 border-dark-primary pointer-events-none transition-all duration-200 hover:scale-110"
          style={{ left: `calc(${percentage}% - 8px)` }}
        />
      </div>
      {/* Scale Labels */}
      <div className="flex justify-between text-xs text-light-tertiary">
        <span>{optional ? 'Cualquiera' : `${min}${unit}`}</span>
        <span>{max}{unit}{max === 100 ? '' : '+'}</span>
      </div>
    </div>
  );
}

// Age bracket options
const AGE_BRACKETS = ['13-17', '18-24', '25-34', '35-44', '45-54', '55+'];

export function FilterPanel({ filters, onChange }: FilterPanelProps) {
  const handleChange = <K extends keyof FilterConfig>(
    key: K,
    value: FilterConfig[K]
  ) => {
    onChange({
      ...filters,
      [key]: value,
    });
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
    <div className="glass rounded-xl border border-dark-border/50 p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-sm font-semibold text-light-primary uppercase tracking-wider">
          Filtros
        </h3>
        {hasChanges && (
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 text-xs text-light-tertiary hover:text-accent-gold transition-colors"
          >
            <RotateCcw className="w-3 h-3" />
            Restablecer
          </button>
        )}
      </div>

      {/* Filter Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {/* Credibility Score */}
        <FilterSlider
          label="Credibilidad Mín."
          value={filters.min_credibility_score}
          min={0}
          max={100}
          step={5}
          defaultValue={70}
          onChange={(value) => handleChange('min_credibility_score', value ?? 70)}
        />

        {/* Spain Audience */}
        <FilterSlider
          label="Audiencia España Mín."
          value={filters.min_spain_audience_pct}
          min={0}
          max={100}
          step={5}
          defaultValue={60}
          onChange={(value) => handleChange('min_spain_audience_pct', value ?? 60)}
        />

        {/* Engagement Rate */}
        <FilterSlider
          label="Engagement Mín."
          value={filters.min_engagement_rate}
          min={0}
          max={15}
          step={0.5}
          defaultValue={0}
          onChange={(value) => handleChange('min_engagement_rate', value)}
          optional
          formatValue={(v) => (v !== undefined ? `${v}%` : 'Cualquiera')}
        />

        {/* Growth Rate */}
        <FilterSlider
          label="Crecimiento 6M Mín."
          value={filters.min_follower_growth_rate}
          min={-20}
          max={50}
          step={5}
          defaultValue={-20}
          onChange={(value) =>
            handleChange('min_follower_growth_rate', value === -20 ? undefined : value)
          }
          optional
          formatValue={(v) =>
            v !== undefined ? `${v > 0 ? '+' : ''}${v}%` : 'Cualquiera'
          }
        />

        {/* Gender Audience Filter */}
        <div className="space-y-3">
          <label className="text-sm font-medium text-light-secondary">
            Género de Audiencia Objetivo
          </label>
          <div className="flex gap-2">
            {(['any', 'female', 'male'] as const).map((gender) => (
              <button
                key={gender}
                onClick={() =>
                  handleChange(
                    'target_audience_gender',
                    gender === 'any' ? undefined : gender
                  )
                }
                className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                  (filters.target_audience_gender === gender) ||
                  (gender === 'any' && !filters.target_audience_gender)
                    ? 'bg-accent-gold text-dark-primary font-medium'
                    : 'bg-dark-tertiary text-light-secondary hover:bg-dark-border'
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
              min={50}
              max={90}
              step={5}
              defaultValue={50}
              onChange={(value) => handleChange('min_target_gender_pct', value)}
            />
          )}
        </div>

        {/* Age Bracket Filter */}
        <div className="space-y-3 sm:col-span-2">
          <label className="text-sm font-medium text-light-secondary">
            Rangos de Edad Objetivo
          </label>
          <div className="flex flex-wrap gap-2">
            {AGE_BRACKETS.map((range) => (
              <button
                key={range}
                onClick={() => toggleAgeRange(range)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                  filters.target_age_ranges?.includes(range)
                    ? 'bg-accent-gold text-dark-primary font-medium'
                    : 'bg-dark-tertiary text-light-secondary hover:bg-dark-border'
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
              min={20}
              max={80}
              step={5}
              defaultValue={30}
              onChange={(value) => handleChange('min_target_age_pct', value)}
            />
          )}
        </div>
      </div>

      {/* Active Filters Summary */}
      <div className="mt-6 pt-4 border-t border-dark-border/50">
        <div className="flex flex-wrap gap-2">
          <span className="text-xs text-light-tertiary">Activos:</span>
          <span className="px-2 py-0.5 rounded-full bg-accent-gold/10 text-accent-gold text-xs">
            Credibilidad ≥ {filters.min_credibility_score}%
          </span>
          <span className="px-2 py-0.5 rounded-full bg-accent-gold/10 text-accent-gold text-xs">
            España ≥ {filters.min_spain_audience_pct}%
          </span>
          {filters.min_engagement_rate !== undefined && (
            <span className="px-2 py-0.5 rounded-full bg-accent-gold/10 text-accent-gold text-xs">
              Engagement ≥ {filters.min_engagement_rate}%
            </span>
          )}
          {filters.min_follower_growth_rate !== undefined && (
            <span className="px-2 py-0.5 rounded-full bg-accent-gold/10 text-accent-gold text-xs">
              Crecimiento ≥ {filters.min_follower_growth_rate > 0 ? '+' : ''}
              {filters.min_follower_growth_rate}%
            </span>
          )}
          {filters.target_audience_gender && (
            <span className="px-2 py-0.5 rounded-full bg-accent-gold/10 text-accent-gold text-xs">
              Audiencia {filters.target_audience_gender === 'female' ? 'femenina' : 'masculina'} ≥{' '}
              {filters.min_target_gender_pct ?? 50}%
            </span>
          )}
          {filters.target_age_ranges && filters.target_age_ranges.length > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-accent-gold/10 text-accent-gold text-xs">
              Edades: {filters.target_age_ranges.join(', ')}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
