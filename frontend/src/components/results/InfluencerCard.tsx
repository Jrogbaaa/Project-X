'use client';

import { useState } from 'react';
import Image from 'next/image';
import {
  ExternalLink, Users, TrendingUp, TrendingDown,
  BadgeCheck, ChevronDown, Copy, Check, AlertTriangle,
} from 'lucide-react';
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
    <div className={cn('px-2.5 py-2 rounded-lg text-center', metricClass)}>
      <div className="text-[9px] font-medium uppercase tracking-wider opacity-70 mb-0.5 flex items-center justify-center gap-0.5">
        {label}
        {icon}
      </div>
      <div className="font-mono font-semibold text-[0.8rem]">{value}</div>
    </div>
  );
}

export function InfluencerCard({
  influencer,
  index = 0,
  isSelected = false,
  onCopy,
  onExpand,
}: InfluencerCardProps) {
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
    if (!isExpanded) onExpand?.();
  };

  const hasAudienceGeo = raw_data.audience_geography && Object.keys(raw_data.audience_geography).length > 0;
  const spainPct = hasAudienceGeo ? (raw_data.audience_geography?.ES || raw_data.audience_geography?.es || 0) : null;
  const growthRate = raw_data.follower_growth_rate_6m;
  const engagementRate = raw_data.engagement_rate;
  const GrowthIcon = growthRate && growthRate > 0 ? TrendingUp : TrendingDown;

  return (
    <div
      className={cn(
        'group relative rounded-xl border overflow-hidden',
        'bg-dark-secondary transition-all duration-280',
        'animate-card-reveal shadow-card',
        isSelected
          ? 'border-ember-warm/45 shadow-ember-glow animate-ember-pulse'
          : 'border-dark-border/60 hover:border-dark-border hover:shadow-card-hover'
      )}
      style={{ animationDelay: `${index * 60}ms` }}
      data-index={index}
    >
      {/* ── Ghost rank number — signature design element ── */}
      <div
        className="ghost-rank absolute top-0 right-3 select-none pointer-events-none"
        style={{ fontSize: '6.5rem' }}
        aria-hidden="true"
      >
        {String(rank_position).padStart(2, '0')}
      </div>

      {/* ── Left accent line (clay) ── */}
      <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-ember-warm/0 group-hover:bg-ember-warm/50 transition-all duration-280 rounded-l-xl" />

      {/* ── Main content ── */}
      <div className="p-5 relative z-10">

        {/* Header row */}
        <div className="flex items-start gap-3 mb-4">

          {/* Rank chip */}
          <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-dark-ash border border-dark-border/60 flex items-center justify-center">
            <span className="font-mono font-bold text-light-secondary text-xs">
              {rank_position}
            </span>
          </div>

          {/* Profile info */}
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {/* Avatar */}
            <div className="relative w-12 h-12 rounded-full overflow-hidden bg-dark-ash flex-shrink-0 ring-2 ring-dark-border/50 group-hover:ring-ember-warm/25 transition-all duration-280">
              {raw_data.profile_picture_url ? (
                <Image
                  src={raw_data.profile_picture_url}
                  alt={raw_data.username}
                  fill
                  className="object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <Users className="h-4 w-4 text-light-tertiary/50" />
                </div>
              )}
            </div>

            {/* Name stack */}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <h3 className="text-[0.95rem] font-semibold text-light-primary truncate">
                  @{raw_data.username}
                </h3>
                {raw_data.is_verified && (
                  <BadgeCheck className="h-4 w-4 text-ice-bright flex-shrink-0" />
                )}
                {raw_data.profile_active === false && (
                  <span
                    title="Este perfil puede no existir en Instagram"
                    className="flex items-center gap-0.5 text-[10px] font-medium text-amber-400/80 bg-amber-400/10 border border-amber-400/20 px-1.5 py-0.5 rounded"
                  >
                    <AlertTriangle className="h-2.5 w-2.5" />
                    No verificado
                  </span>
                )}
                <button
                  onClick={() => handleCopy(`@${raw_data.username}`, 'username')}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-dark-ash transition-all"
                  aria-label="Copiar usuario"
                  tabIndex={0}
                >
                  {copiedField === 'username' ? (
                    <Check className="w-3.5 h-3.5 text-metric-excellent" />
                  ) : (
                    <Copy className="w-3.5 h-3.5 text-light-tertiary" />
                  )}
                </button>
              </div>
              {raw_data.display_name && (
                <p className="text-light-secondary text-xs truncate mt-0.5">{raw_data.display_name}</p>
              )}
              <p className="text-light-tertiary text-xs mt-0.5">
                <span className="font-mono text-light-secondary">
                  {raw_data.follower_count > 0 ? formatNumber(raw_data.follower_count) : 'N/A'}
                </span>{' '}
                seguidores
              </p>

              {/* Interest tags */}
              {raw_data.interests && raw_data.interests.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {raw_data.interests.slice(0, 2).map((interest, i) => (
                    <span
                      key={i}
                      className="px-1.5 py-0.5 text-[10px] rounded bg-ice-bright/[0.08] text-ice-bright border border-ice-bright/15"
                    >
                      {interest}
                    </span>
                  ))}
                  {raw_data.interests.length > 2 && (
                    <span className="px-1.5 py-0.5 text-[10px] rounded bg-dark-ash text-light-tertiary border border-dark-border/50">
                      +{raw_data.interests.length - 2}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Match score */}
          <div className="flex-shrink-0 text-right">
            <div className="text-[9px] text-light-tertiary/60 uppercase tracking-widest mb-0.5">
              Match
            </div>
            <div className={cn('text-[1.6rem] font-mono font-bold leading-none', getMatchScoreClass(relevance_score))}>
              {(relevance_score * 100).toFixed(0)}
              <span className="text-xs font-normal ml-0.5">%</span>
            </div>
          </div>
        </div>

        {/* Metrics row */}
        <div className="grid grid-cols-4 gap-2 mb-4">
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
              <GrowthIcon className="w-2.5 h-2.5" />
            )}
          />
        </div>

        {/* Expand toggle */}
        <button
          onClick={handleExpandToggle}
          className="w-full flex items-center justify-center gap-1.5 py-1.5 text-xs text-light-tertiary/60 hover:text-light-secondary transition-colors"
        >
          <span>{isExpanded ? 'Ocultar detalles' : 'Ver detalles'}</span>
          <ChevronDown
            className={cn(
              'w-3.5 h-3.5 transition-transform duration-280',
              isExpanded && 'rotate-180'
            )}
          />
        </button>
      </div>

      {/* ── Expandable details ── */}
      <div
        className={cn(
          'overflow-hidden transition-all duration-300 ease-spring',
          isExpanded ? 'max-h-[650px] opacity-100' : 'max-h-0 opacity-0'
        )}
      >
        <div className="px-5 pb-5 space-y-5 border-t border-dark-border/40 pt-5">

          {/* Bio */}
          {raw_data.bio && (
            <p className="text-sm text-light-secondary leading-relaxed">{raw_data.bio}</p>
          )}

          {/* Content niches */}
          {raw_data.interests && raw_data.interests.length > 0 && (
            <div>
              <h4 className="text-[10px] font-semibold text-ember-warm/70 uppercase tracking-[0.10em] mb-2">
                Nichos de Contenido
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {raw_data.interests.map((interest, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 text-xs rounded bg-ice-bright/[0.08] text-ice-bright border border-ice-bright/15"
                  >
                    {interest}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Demographics */}
          <AudienceChart
            genders={raw_data.audience_genders}
            ageDistribution={raw_data.audience_age_distribution}
          />

          {/* Score breakdown */}
          <ScoreBreakdown scores={scores} />
        </div>
      </div>

      {/* ── Footer ── */}
      <div className="px-5 py-3 bg-dark-tertiary/40 border-t border-dark-border/30 flex items-center justify-between">
        <p className="text-xs text-light-tertiary/60">
          <span className="font-mono text-light-secondary">{raw_data.avg_likes > 0 ? formatNumber(raw_data.avg_likes) : 'N/A'}</span>{' '}
          likes ·{' '}
          <span className="font-mono text-light-secondary">{raw_data.avg_comments > 0 ? formatNumber(raw_data.avg_comments) : 'N/A'}</span>{' '}
          comentarios
        </p>
        <div className="flex items-center gap-3">
          {raw_data.mediakit_url && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => handleCopy(raw_data.mediakit_url!, 'mediakit')}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-dark-ash transition-all"
                aria-label="Copiar URL MediaKit"
                tabIndex={0}
              >
                {copiedField === 'mediakit' ? (
                  <Check className="w-3 h-3 text-metric-excellent" />
                ) : (
                  <Copy className="w-3 h-3 text-light-tertiary" />
                )}
              </button>
              <a
                href={raw_data.mediakit_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-light-secondary hover:text-light-primary text-xs font-medium transition-colors"
                aria-label={`MediaKit de ${raw_data.username}`}
                tabIndex={0}
              >
                MediaKit
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          )}
          <a
            href={raw_data.profile_url || `https://instagram.com/${raw_data.username}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-ember-warm hover:text-ember-hot text-xs font-medium transition-colors"
            aria-label={`Perfil de ${raw_data.username}`}
            tabIndex={0}
          >
            Perfil
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>
    </div>
  );
}
