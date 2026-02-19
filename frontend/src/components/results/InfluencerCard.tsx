'use client';

import { useState } from 'react';
import Image from 'next/image';
import { ExternalLink, Users, TrendingUp, TrendingDown, BadgeCheck, ChevronDown, Copy, Check } from 'lucide-react';
import { RankedInfluencer } from '@/types/search';
import { formatNumber, formatPercentage, cn, getMetricClass, getMatchScoreClass } from '@/lib/utils';
import { AudienceChart } from './AudienceChart';
import { ScoreBreakdown } from './ScoreBreakdown';

interface InfluencerCardProps {
  influencer: RankedInfluencer;
  index?: number;
  isSelected?: boolean;
  onCopy?: (message: string) => void;
  onExpand?: () => void;
}

interface MetricPillProps {
  label: string;
  value: string;
  metricClass: string;
  icon?: React.ReactNode;
}

function MetricPill({ label, value, metricClass, icon }: MetricPillProps) {
  return (
    <div className={cn('px-3 py-2 rounded-lg text-center', metricClass)}>
      <div className="text-[10px] font-medium uppercase tracking-wider opacity-80 mb-0.5 flex items-center justify-center gap-1">
        {label}
        {icon}
      </div>
      <div className="font-mono font-semibold text-sm">{value}</div>
    </div>
  );
}

export function InfluencerCard({ influencer, index = 0, isSelected = false, onCopy, onExpand }: InfluencerCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copiedField, setCopiedField] = useState<'username' | 'mediakit' | null>(null);
  const { raw_data, scores, relevance_score, rank_position } = influencer;

  const handleCopy = async (text: string, field: 'username' | 'mediakit') => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      onCopy?.(field === 'username' ? 'Usuario copiado' : 'URL MediaKit copiada');
      setTimeout(() => setCopiedField(null), 1500);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleExpandToggle = () => {
    setIsExpanded(!isExpanded);
    if (!isExpanded) {
      onExpand?.();
    }
  };

  // Check if we have actual audience geography data (not just empty object)
  const hasAudienceGeo = raw_data.audience_geography && Object.keys(raw_data.audience_geography).length > 0;
  const spainPct = hasAudienceGeo ? (raw_data.audience_geography?.ES || raw_data.audience_geography?.es || 0) : null;
  const growthRate = raw_data.follower_growth_rate_6m;
  const engagementRate = raw_data.engagement_rate;

  const GrowthIcon = growthRate && growthRate > 0 ? TrendingUp : TrendingDown;

  return (
    <div
      className={cn(
        'group rounded-xl border overflow-hidden',
        'bg-gradient-to-b from-dark-secondary to-dark-tertiary/50',
        'hover:border-ember-core/40 transition-all duration-300',
        'animate-card-reveal',
        'shadow-card',
        isSelected
          ? 'border-ember-core/50 ring-2 ring-ember-core/20 shadow-glow-gold animate-ember-pulse'
          : 'border-dark-border/40 hover:shadow-card-hover'
      )}
      style={{ animationDelay: `${index * 60}ms` }}
      data-index={index}
    >
      {/* Main Card Content */}
      <div className="p-6">
        {/* Header Row */}
        <div className="flex items-start gap-4 mb-5">
          {/* Rank Badge - Ember Core */}
          <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-gradient-to-br from-ember-hot/90 to-ember-core flex items-center justify-center shadow-lg shadow-ember-core/30">
            <span className="font-mono font-bold text-dark-void text-sm">
              {rank_position}
            </span>
          </div>

          {/* Profile Info */}
          <div className="flex items-center gap-4 flex-1 min-w-0">
            {/* Avatar */}
            <div className="relative w-14 h-14 rounded-full overflow-hidden bg-dark-tertiary flex-shrink-0 ring-2 ring-dark-border/60 group-hover:ring-ember-core/40 transition-all duration-300">
              {raw_data.profile_picture_url ? (
                <Image
                  src={raw_data.profile_picture_url}
                  alt={raw_data.username}
                  fill
                  className="object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <Users className="h-5 w-5 text-light-tertiary" />
                </div>
              )}
            </div>

            {/* Name Stack */}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold text-light-primary truncate">
                  @{raw_data.username}
                </h3>
                {raw_data.is_verified && (
                  <BadgeCheck className="h-5 w-5 text-ice-bright flex-shrink-0" />
                )}
                <button
                  onClick={() => handleCopy(`@${raw_data.username}`, 'username')}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-white/10 transition-all"
                  aria-label="Copiar usuario"
                  tabIndex={0}
                >
                  {copiedField === 'username' ? (
                    <Check className="w-4 h-4 text-metric-excellent" />
                  ) : (
                    <Copy className="w-4 h-4 text-light-tertiary" />
                  )}
                </button>
              </div>
              {raw_data.display_name && (
                <p className="text-light-secondary text-sm truncate mt-0.5">
                  {raw_data.display_name}
                </p>
              )}
              <p className="text-light-tertiary text-sm mt-1">
                <span className="font-mono font-medium text-light-secondary">
                  {raw_data.follower_count > 0 ? formatNumber(raw_data.follower_count) : 'N/A'}
                </span>{' '}
                seguidores
              </p>
              {/* Niche Tags - Show first 2 */}
              {raw_data.interests && raw_data.interests.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {raw_data.interests.slice(0, 2).map((interest, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 text-[10px] rounded-full bg-ice-soft/10 text-ice-soft border border-ice-soft/20"
                    >
                      {interest}
                    </span>
                  ))}
                  {raw_data.interests.length > 2 && (
                    <span className="px-2 py-0.5 text-[10px] rounded-full bg-dark-ash text-light-tertiary">
                      +{raw_data.interests.length - 2}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Match Score */}
          <div className="flex-shrink-0 text-right">
            <div className="text-[10px] text-light-tertiary uppercase tracking-wider mb-1">
              Match
            </div>
            <div className={cn('text-2xl font-mono font-bold', getMatchScoreClass(relevance_score))}>
              {(relevance_score * 100).toFixed(0)}
              <span className="text-sm">%</span>
            </div>
          </div>
        </div>

        {/* Metrics Row */}
        <div className="grid grid-cols-4 gap-3 mb-5">
          <MetricPill
            label="Cred"
            value={raw_data.credibility_score ? `${raw_data.credibility_score.toFixed(0)}%` : 'N/A'}
            metricClass={getMetricClass(raw_data.credibility_score, 'credibility')}
          />
          <MetricPill
            label="Eng"
            value={formatPercentage(engagementRate, 1)}
            metricClass={getMetricClass(engagementRate, 'engagement')}
          />
          <MetricPill
            label="España"
            value={spainPct !== null ? `${spainPct.toFixed(0)}%` : 'N/A'}
            metricClass={getMetricClass(spainPct, 'spain')}
          />
          <MetricPill
            label="Crec."
            value={growthRate ? `${(growthRate * 100).toFixed(0)}%` : 'N/A'}
            metricClass={getMetricClass(growthRate ? growthRate * 100 : null, 'growth')}
            icon={growthRate !== null && growthRate !== undefined && (
              <GrowthIcon className="w-3 h-3" />
            )}
          />
        </div>

        {/* Expand Toggle */}
        <button
          onClick={handleExpandToggle}
          className="w-full flex items-center justify-center gap-2 py-2 text-sm text-light-tertiary hover:text-light-secondary transition-colors"
        >
          <span>{isExpanded ? 'Ocultar detalles' : 'Ver detalles'}</span>
          <ChevronDown
            className={cn(
              'w-4 h-4 transition-transform duration-300',
              isExpanded && 'rotate-180'
            )}
          />
        </button>
      </div>

      {/* Expandable Details */}
      <div
        className={cn(
          'overflow-hidden transition-all duration-300 ease-spring',
          isExpanded ? 'max-h-[600px] opacity-100' : 'max-h-0 opacity-0'
        )}
      >
        <div className="px-6 pb-6 space-y-6 border-t border-dark-border/30 pt-6">
          {/* Bio */}
          {raw_data.bio && (
            <p className="text-sm text-light-secondary leading-relaxed">
              {raw_data.bio}
            </p>
          )}

          {/* Content Niches */}
          {raw_data.interests && raw_data.interests.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-ember-glow/80 uppercase tracking-wider mb-2">
                Nichos de Contenido
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {raw_data.interests.map((interest, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 text-xs rounded-full bg-ice-soft/10 text-ice-soft border border-ice-soft/20"
                  >
                    {interest}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Audience Demographics */}
          <AudienceChart
            genders={raw_data.audience_genders}
            ageDistribution={raw_data.audience_age_distribution}
          />

          {/* Score Breakdown */}
          <ScoreBreakdown scores={scores} />
        </div>
      </div>

      {/* Footer */}
      <div className="px-6 py-4 bg-dark-ash/40 border-t border-dark-border/20 flex items-center justify-between">
        <div className="text-sm text-light-tertiary">
          Media: <span className="font-mono text-light-secondary">{raw_data.avg_likes > 0 ? formatNumber(raw_data.avg_likes) : 'N/A'}</span> likes,{' '}
          <span className="font-mono text-light-secondary">{raw_data.avg_comments > 0 ? formatNumber(raw_data.avg_comments) : 'N/A'}</span> comentarios
        </div>
        <div className="flex items-center gap-3">
          {raw_data.mediakit_url && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => handleCopy(raw_data.mediakit_url!, 'mediakit')}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-white/10 transition-all"
                aria-label="Copiar URL MediaKit"
                tabIndex={0}
              >
                {copiedField === 'mediakit' ? (
                  <Check className="w-3.5 h-3.5 text-metric-excellent" />
                ) : (
                  <Copy className="w-3.5 h-3.5 text-light-tertiary" />
                )}
              </button>
              <a
                href={raw_data.mediakit_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-light-secondary hover:text-light-primary text-sm font-medium transition-colors"
                aria-label={`Ver MediaKit de ${raw_data.username}`}
                tabIndex={0}
              >
                MediaKit
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>
          )}
          <a
            href={raw_data.profile_url || `https://instagram.com/${raw_data.username}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-ember-warm hover:text-ember-hot text-sm font-medium transition-colors"
            aria-label={`Ver perfil de Instagram de ${raw_data.username}`}
            tabIndex={0}
          >
            Perfil
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>
    </div>
  );
}
