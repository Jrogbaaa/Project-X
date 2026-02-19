'use client';

import { useState } from 'react';
import Image from 'next/image';
import { ExternalLink, Users, BadgeCheck, Copy, Check, TrendingUp, TrendingDown } from 'lucide-react';
import { RankedInfluencer } from '@/types/search';
import { formatNumber, cn, getMetricClass, getMatchScoreClass } from '@/lib/utils';

interface InfluencerRowProps {
  influencer: RankedInfluencer;
  index?: number;
  isSelected?: boolean;
  onCopy?: (message: string) => void;
}

export function InfluencerRow({ influencer, index = 0, isSelected = false, onCopy }: InfluencerRowProps) {
  const [copiedField, setCopiedField] = useState<'username' | 'mediakit' | null>(null);
  const { raw_data, relevance_score, rank_position } = influencer;

  const spainPct = raw_data.audience_geography?.ES || raw_data.audience_geography?.es || 0;
  const growthRate = raw_data.follower_growth_rate_6m;
  const GrowthIcon = growthRate && growthRate > 0 ? TrendingUp : TrendingDown;

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

  return (
    <div
      className={cn(
        'group flex items-center gap-4 px-4 py-3 rounded-lg border transition-all duration-200',
        'hover:bg-dark-ash/30 animate-card-reveal',
        isSelected
          ? 'bg-ember-core/5 border-ember-core/40 ring-1 ring-ember-core/20 shadow-sm shadow-ember-core/10'
          : 'bg-dark-secondary/40 border-dark-border/40 hover:border-ember-core/30'
      )}
      style={{ animationDelay: `${index * 40}ms` }}
      data-index={index}
    >
      {/* Rank */}
      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-ember-hot/80 to-ember-core flex items-center justify-center shadow-sm shadow-ember-core/30">
        <span className="font-mono font-bold text-dark-void text-sm">
          {rank_position}
        </span>
      </div>

      {/* Avatar */}
      <div className="relative w-10 h-10 rounded-full overflow-hidden bg-dark-tertiary flex-shrink-0 ring-1 ring-dark-border/50 group-hover:ring-ember-core/30 transition-all">
        {raw_data.profile_picture_url ? (
          <Image
            src={raw_data.profile_picture_url}
            alt={raw_data.username}
            fill
            className="object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Users className="h-4 w-4 text-light-tertiary" />
          </div>
        )}
      </div>

      {/* Username & Followers */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="font-semibold text-light-primary truncate text-sm">
            @{raw_data.username}
          </span>
          {raw_data.is_verified && (
            <BadgeCheck className="h-3.5 w-3.5 text-ice-bright flex-shrink-0" />
          )}
          <button
            onClick={() => handleCopy(`@${raw_data.username}`, 'username')}
            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-white/10 transition-all ml-1"
            aria-label="Copiar usuario"
            tabIndex={0}
          >
            {copiedField === 'username' ? (
              <Check className="w-3 h-3 text-metric-excellent" />
            ) : (
              <Copy className="w-3 h-3 text-light-tertiary" />
            )}
          </button>
        </div>
        <p className="text-light-tertiary text-xs">
          <span className="font-mono">{formatNumber(raw_data.follower_count)}</span> seguidores
        </p>
      </div>

      {/* Match Score */}
      <div className="flex-shrink-0 text-center w-16">
        <div className={cn('text-lg font-mono font-bold', getMatchScoreClass(relevance_score))}>
          {(relevance_score * 100).toFixed(0)}%
        </div>
        <div className="text-[10px] text-light-tertiary uppercase tracking-wider">Match</div>
      </div>

      {/* Metrics - Compact */}
      <div className="hidden md:flex items-center gap-3 flex-shrink-0">
        <div className={cn('px-2 py-1 rounded text-xs font-mono', getMetricClass(raw_data.credibility_score, 'credibility'))}>
          {raw_data.credibility_score ? `${raw_data.credibility_score.toFixed(0)}%` : 'N/A'}
        </div>
        <div className={cn('px-2 py-1 rounded text-xs font-mono', getMetricClass(raw_data.engagement_rate, 'engagement'))}>
          {raw_data.engagement_rate ? `${raw_data.engagement_rate.toFixed(1)}%` : 'N/A'}
        </div>
        <div className={cn('px-2 py-1 rounded text-xs font-mono', getMetricClass(spainPct, 'spain'))}>
          {spainPct.toFixed(0)}% ES
        </div>
        <div className={cn('px-2 py-1 rounded text-xs font-mono flex items-center gap-1', getMetricClass(growthRate ? growthRate * 100 : null, 'growth'))}>
          {growthRate !== null && growthRate !== undefined && (
            <GrowthIcon className="w-3 h-3" />
          )}
          {growthRate ? `${(growthRate * 100).toFixed(0)}%` : 'N/A'}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {raw_data.mediakit_url && (
          <>
            <button
              onClick={() => handleCopy(raw_data.mediakit_url!, 'mediakit')}
              className="opacity-0 group-hover:opacity-100 p-1.5 rounded hover:bg-white/10 transition-all"
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
              className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium text-light-secondary hover:text-light-primary hover:bg-white/5 transition-all"
              aria-label={`Ver MediaKit de ${raw_data.username}`}
              tabIndex={0}
            >
              MediaKit
              <ExternalLink className="h-3 w-3" />
            </a>
          </>
        )}
        <a
          href={raw_data.profile_url || `https://instagram.com/${raw_data.username}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium text-ember-warm hover:text-ember-hot hover:bg-ember-core/10 transition-all"
          aria-label={`Ver perfil de Instagram de ${raw_data.username}`}
          tabIndex={0}
        >
          Perfil
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </div>
  );
}
