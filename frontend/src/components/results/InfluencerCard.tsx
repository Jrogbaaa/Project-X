'use client';

import { useState } from 'react';
import Image from 'next/image';
import { ExternalLink, Users, TrendingUp, TrendingDown, BadgeCheck, ChevronDown } from 'lucide-react';
import { RankedInfluencer } from '@/types/search';
import { formatNumber, formatPercentage, cn, getMetricClass, getMatchScoreClass } from '@/lib/utils';
import { AudienceChart } from './AudienceChart';
import { ScoreBreakdown } from './ScoreBreakdown';

interface InfluencerCardProps {
  influencer: RankedInfluencer;
  index?: number;
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

export function InfluencerCard({ influencer, index = 0 }: InfluencerCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { raw_data, scores, relevance_score, rank_position } = influencer;

  const spainPct = raw_data.audience_geography?.ES || raw_data.audience_geography?.es || 0;
  const growthRate = raw_data.follower_growth_rate_6m;
  const engagementRate = raw_data.engagement_rate;

  const GrowthIcon = growthRate && growthRate > 0 ? TrendingUp : TrendingDown;

  return (
    <div
      className={cn(
        'group bg-dark-secondary rounded-xl border border-dark-border/50 overflow-hidden',
        'hover:border-accent-gold/30 hover:shadow-card-hover transition-all duration-300',
        'animate-cascade'
      )}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      {/* Main Card Content */}
      <div className="p-5">
        {/* Header Row */}
        <div className="flex items-start gap-4 mb-4">
          {/* Rank Badge */}
          <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-accent-gold/10 border border-accent-gold/20 flex items-center justify-center">
            <span className="font-mono font-bold text-accent-gold text-sm">
              {rank_position}
            </span>
          </div>

          {/* Profile Info */}
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {/* Avatar */}
            <div className="relative w-12 h-12 rounded-full overflow-hidden bg-dark-tertiary flex-shrink-0 ring-2 ring-dark-border group-hover:ring-accent-gold/30 transition-all">
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
              <div className="flex items-center gap-1.5">
                <h3 className="font-semibold text-light-primary truncate">
                  @{raw_data.username}
                </h3>
                {raw_data.is_verified && (
                  <BadgeCheck className="h-4 w-4 text-accent-gold flex-shrink-0" />
                )}
              </div>
              {raw_data.display_name && (
                <p className="text-light-tertiary text-sm truncate">
                  {raw_data.display_name}
                </p>
              )}
              <p className="text-light-secondary text-xs mt-0.5">
                <span className="font-mono">{formatNumber(raw_data.follower_count)}</span> followers
              </p>
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
            label="Spain"
            value={`${spainPct.toFixed(0)}%`}
            metricClass={getMetricClass(spainPct, 'spain')}
          />
          <MetricPill
            label="Growth"
            value={growthRate ? `${(growthRate * 100).toFixed(0)}%` : 'N/A'}
            metricClass={getMetricClass(growthRate ? growthRate * 100 : null, 'growth')}
            icon={growthRate !== null && growthRate !== undefined && (
              <GrowthIcon className="w-3 h-3" />
            )}
          />
        </div>

        {/* Expand Toggle */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full flex items-center justify-center gap-2 py-2 text-sm text-light-tertiary hover:text-light-secondary transition-colors"
        >
          <span>{isExpanded ? 'Hide details' : 'View details'}</span>
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
        <div className="px-5 pb-5 space-y-6 border-t border-dark-border/50 pt-5">
          {/* Bio */}
          {raw_data.bio && (
            <p className="text-sm text-light-secondary leading-relaxed">
              {raw_data.bio}
            </p>
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
      <div className="px-5 py-3 bg-dark-tertiary/50 border-t border-dark-border/30 flex items-center justify-between">
        <div className="text-xs text-light-tertiary">
          Avg: <span className="font-mono text-light-secondary">{formatNumber(raw_data.avg_likes)}</span> likes,{' '}
          <span className="font-mono text-light-secondary">{formatNumber(raw_data.avg_comments)}</span> comments
        </div>
        <div className="flex items-center gap-3">
          {raw_data.mediakit_url && (
            <a
              href={raw_data.mediakit_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-light-secondary hover:text-light-primary text-sm font-medium transition-colors"
              aria-label={`View MediaKit for ${raw_data.username}`}
              tabIndex={0}
            >
              MediaKit
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
          <a
            href={raw_data.profile_url || `https://instagram.com/${raw_data.username}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-accent-gold hover:text-accent-gold-light text-sm font-medium transition-colors"
            aria-label={`View Instagram profile for ${raw_data.username}`}
            tabIndex={0}
          >
            Profile
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>
    </div>
  );
}
