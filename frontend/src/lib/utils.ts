import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(value: number): string {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`;
  }
  return value.toString();
}

export function formatPercentage(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined) {
    return 'N/A';
  }
  // If value is already a percentage (0-100), use as is
  // If value is a decimal (0-1), convert to percentage
  const percentage = value > 1 ? value : value * 100;
  return `${percentage.toFixed(decimals)}%`;
}

// Dark theme metric colors
export function getMetricClass(score: number | null | undefined, type: 'credibility' | 'engagement' | 'growth' | 'spain' = 'credibility'): string {
  if (score === null || score === undefined) return 'metric-warning';

  // Normalize score to 0-100 if it's a decimal
  const normalizedScore = score <= 1 ? score * 100 : score;

  switch (type) {
    case 'credibility':
      if (normalizedScore >= 80) return 'metric-excellent';
      if (normalizedScore >= 70) return 'metric-good';
      if (normalizedScore >= 60) return 'metric-warning';
      return 'metric-poor';
    case 'engagement':
      // Engagement rate thresholds (already in percentage form 0-15)
      const engRate = score <= 1 ? score * 100 : score;
      if (engRate >= 4) return 'metric-excellent';
      if (engRate >= 2.5) return 'metric-good';
      if (engRate >= 1.5) return 'metric-warning';
      return 'metric-poor';
    case 'growth':
      // Growth rate thresholds
      const growthRate = score <= 1 ? score * 100 : score;
      if (growthRate >= 10) return 'metric-excellent';
      if (growthRate >= 0) return 'metric-good';
      if (growthRate >= -10) return 'metric-warning';
      return 'metric-poor';
    case 'spain':
      if (normalizedScore >= 70) return 'metric-excellent';
      if (normalizedScore >= 60) return 'metric-good';
      if (normalizedScore >= 40) return 'metric-warning';
      return 'metric-poor';
    default:
      return 'metric-good';
  }
}

// For match/relevance score
export function getMatchScoreClass(score: number): string {
  if (score >= 0.8) return 'text-metric-excellent';
  if (score >= 0.6) return 'text-accent-gold';
  if (score >= 0.4) return 'text-metric-warning';
  return 'text-metric-poor';
}

// Legacy functions for compatibility
export function getScoreColor(score: number): string {
  if (score >= 0.8) return 'text-metric-excellent';
  if (score >= 0.6) return 'text-accent-gold';
  if (score >= 0.4) return 'text-metric-warning';
  return 'text-metric-poor';
}

export function getScoreBgColor(score: number): string {
  if (score >= 0.8) return 'metric-excellent';
  if (score >= 0.6) return 'metric-good';
  if (score >= 0.4) return 'metric-warning';
  return 'metric-poor';
}

export function getMetricColor(value: number, thresholds: { good: number; ok: number }): string {
  if (value >= thresholds.good) return 'text-metric-excellent';
  if (value >= thresholds.ok) return 'text-accent-gold';
  return 'text-metric-poor';
}
