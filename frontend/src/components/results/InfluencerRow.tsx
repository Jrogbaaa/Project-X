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
        'group flex items-center gap-3 px-4 py-3 transition-all duration-200 animate-card-reveal',
        isSelected
          ? 'bg-ember-warm/[0.05] border-l-2 border-ember-warm/50'
          : 'bg-transparent hover:bg-dark-ash/30'
      )}
      style={{ animationDelay: `${index * 40}ms` }}
      data-index={index}
    >
      {/* Rank */}
      <div className="flex-shrink-0 w-7 h-7 rounded-md bg-dark-ash border border-dark-border/50 flex items-center justify-center">
        <span className="font-mono font-bold text-light-tertiary text-[11px]">
          {rank_position}
        </span>
      </div>

      {/* Avatar */}
      <div className="relative w-9 h-9 rounded-full overflow-hidden bg-dark-ash flex-shrink-0 ring-1 ring-dark-border/40 group-hover:ring-ember-warm/20 transition-all">
        {raw_data.profile_picture_url ? (
          <Image
            src={raw_data.profile_picture_url}
            alt={raw_data.username}
            fill
            className="object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Users className="h-3.5 w-3.5 text-light-tertiary/50" />
          </div>
        )}
      </div>

      {/* Username + followers */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1">
          <span className="font-medium text-light-primary truncate text-sm">
            @{raw_data.username}
          </span>
          {raw_data.is_verified && (
            <BadgeCheck className="h-3.5 w-3.5 text-ice-bright flex-shrink-0" />
          )}
          <button
            onClick={() => handleCopy(`@${raw_data.username}`, 'username')}
            className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-dark-ash transition-all ml-0.5"
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
        <p className="text-light-tertiary/60 text-[11px]">
          <span className="font-mono">{formatNumber(raw_data.follower_count)}</span> seguidores
        </p>
      </div>

      {/* Match score */}
      <div className="flex-shrink-0 text-center w-14">
        <div className={cn('text-base font-mono font-bold', getMatchScoreClass(relevance_score))}>
          {(relevance_score * 100).toFixed(0)}%
        </div>
        <div className="text-[9px] text-light-tertiary/50 uppercase tracking-wider">Match</div>
      </div>

      {/* Compact metrics */}
      <div className="hidden md:flex items-center gap-2 flex-shrink-0">
        <div className={cn('px-2 py-1 rounded text-[11px] font-mono', getMetricClass(raw_data.credibility_score, 'credibility'))}>
          {raw_data.credibility_score ? `${raw_data.credibility_score.toFixed(0)}%` : 'N/A'}
        </div>
        <div className={cn('px-2 py-1 rounded text-[11px] font-mono', getMetricClass(raw_data.engagement_rate, 'engagement'))}>
          {raw_data.engagement_rate ? `${raw_data.engagement_rate.toFixed(1)}%` : 'N/A'}
        </div>
        <div className={cn('px-2 py-1 rounded text-[11px] font-mono', getMetricClass(spainPct, 'spain'))}>
          {spainPct.toFixed(0)}% ES
        </div>
        <div className={cn('px-2 py-1 rounded text-[11px] font-mono flex items-center gap-0.5', getMetricClass(growthRate ? growthRate * 100 : null, 'growth'))}>
          {growthRate !== null && growthRate !== undefined && (
            <GrowthIcon className="w-2.5 h-2.5" />
          )}
          {growthRate ? `${(growthRate * 100).toFixed(0)}%` : 'N/A'}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        {raw_data.mediakit_url && (
          <>
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
              className="flex items-center gap-0.5 px-2 py-1 rounded text-[11px] font-medium text-light-secondary hover:text-light-primary hover:bg-dark-ash transition-all"
              aria-label={`MediaKit de ${raw_data.username}`}
              tabIndex={0}
            >
              Kit
              <ExternalLink className="h-2.5 w-2.5" />
            </a>
          </>
        )}
        <a
          href={raw_data.profile_url || `https://instagram.com/${raw_data.username}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-0.5 px-2 py-1 rounded text-[11px] font-medium text-ember-warm hover:text-ember-hot hover:bg-ember-warm/[0.08] transition-all"
          aria-label={`Perfil de ${raw_data.username}`}
          tabIndex={0}
        >
          Perfil
          <ExternalLink className="h-2.5 w-2.5" />
        </a>
      </div>
    </div>
  );
}
