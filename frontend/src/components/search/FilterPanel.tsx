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
    : 'Any';

  const percentage = value !== undefined
    ? ((value - min) / (max - min)) * 100
    : 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-light-secondary">
          {label}
          {optional && <span className="text-light-tertiary ml-1">(optional)</span>}
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
        <span>{optional ? 'Any' : `${min}${unit}`}</span>
        <span>{max}{unit}{max === 100 ? '' : '+'}</span>
      </div>
    </div>
  );
}

export function FilterPanel({ filters, onChange }: FilterPanelProps) {
  const handleChange = (key: keyof FilterConfig, value: number | undefined) => {
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

  const hasChanges =
    filters.min_credibility_score !== 70 ||
    filters.min_spain_audience_pct !== 60 ||
    filters.min_engagement_rate !== undefined ||
    filters.min_follower_growth_rate !== undefined;

  return (
    <div className="glass rounded-xl border border-dark-border/50 p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-sm font-semibold text-light-primary uppercase tracking-wider">
          Filters
        </h3>
        {hasChanges && (
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 text-xs text-light-tertiary hover:text-accent-gold transition-colors"
          >
            <RotateCcw className="w-3 h-3" />
            Reset
          </button>
        )}
      </div>

      {/* Filter Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {/* Credibility Score */}
        <FilterSlider
          label="Min Credibility"
          value={filters.min_credibility_score}
          min={0}
          max={100}
          step={5}
          defaultValue={70}
          onChange={(value) => handleChange('min_credibility_score', value ?? 70)}
        />

        {/* Spain Audience */}
        <FilterSlider
          label="Min Spain Audience"
          value={filters.min_spain_audience_pct}
          min={0}
          max={100}
          step={5}
          defaultValue={60}
          onChange={(value) => handleChange('min_spain_audience_pct', value ?? 60)}
        />

        {/* Engagement Rate */}
        <FilterSlider
          label="Min Engagement Rate"
          value={filters.min_engagement_rate}
          min={0}
          max={15}
          step={0.5}
          defaultValue={0}
          onChange={(value) => handleChange('min_engagement_rate', value)}
          optional
          formatValue={(v) => (v !== undefined ? `${v}%` : 'Any')}
        />

        {/* Growth Rate */}
        <FilterSlider
          label="Min 6M Growth"
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
            v !== undefined ? `${v > 0 ? '+' : ''}${v}%` : 'Any'
          }
        />
      </div>

      {/* Active Filters Summary */}
      <div className="mt-6 pt-4 border-t border-dark-border/50">
        <div className="flex flex-wrap gap-2">
          <span className="text-xs text-light-tertiary">Active:</span>
          <span className="px-2 py-0.5 rounded-full bg-accent-gold/10 text-accent-gold text-xs">
            Credibility ≥ {filters.min_credibility_score}%
          </span>
          <span className="px-2 py-0.5 rounded-full bg-accent-gold/10 text-accent-gold text-xs">
            Spain ≥ {filters.min_spain_audience_pct}%
          </span>
          {filters.min_engagement_rate !== undefined && (
            <span className="px-2 py-0.5 rounded-full bg-accent-gold/10 text-accent-gold text-xs">
              Engagement ≥ {filters.min_engagement_rate}%
            </span>
          )}
          {filters.min_follower_growth_rate !== undefined && (
            <span className="px-2 py-0.5 rounded-full bg-accent-gold/10 text-accent-gold text-xs">
              Growth ≥ {filters.min_follower_growth_rate > 0 ? '+' : ''}
              {filters.min_follower_growth_rate}%
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
