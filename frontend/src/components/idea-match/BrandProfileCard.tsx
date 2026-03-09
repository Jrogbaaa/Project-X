'use client';

import { BrandAttributes } from '@/types/ideaMatch';

interface BrandProfileCardProps {
  attrs: BrandAttributes;
  archetype: string;
  archetypeRationale: string;
  brandVertical: string;
  brandSummary: string;
}

export function BrandProfileCard({
  attrs,
  archetype,
  archetypeRationale,
  brandVertical,
  brandSummary,
}: BrandProfileCardProps) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--parchment)] p-6 shadow-[var(--shadow-sm)]">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--clay)] mb-1">
            Brand Profile
          </p>
          <h2 className="font-serif text-2xl text-[var(--slate)] font-[400]">
            {attrs.brand_name}
          </h2>
          <p className="text-[var(--smoke)] text-sm mt-1 leading-relaxed max-w-[500px]">
            {brandVertical}
          </p>
        </div>

        {/* Archetype badge */}
        <div className="text-right shrink-0">
          <p className="text-[10px] uppercase tracking-wider text-[var(--mist)] mb-1">Archetype</p>
          <span className="inline-block px-3 py-1 rounded-lg bg-[var(--clay)] text-white text-sm font-medium capitalize">
            {archetype}
          </span>
        </div>
      </div>

      {/* Brand truth */}
      <div className="mb-4 pb-4 border-b border-[var(--border)]">
        <p className="text-[10px] uppercase tracking-wider text-[var(--mist)] mb-1.5">Brand Truth</p>
        <p className="text-[var(--charcoal)] text-sm leading-relaxed italic font-serif">
          &ldquo;{brandSummary}&rdquo;
        </p>
      </div>

      {/* Archetype rationale */}
      <div className="mb-4 pb-4 border-b border-[var(--border)]">
        <p className="text-[10px] uppercase tracking-wider text-[var(--mist)] mb-1.5">Why {archetype}?</p>
        <p className="text-[var(--smoke)] text-sm leading-relaxed">{archetypeRationale}</p>
      </div>

      {/* Attribute pills */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <AttributeChip label="Category" value={attrs.category.replace(/_/g, ' ')} />
        <AttributeChip label="Audience" value={attrs.audience.replace(/_/g, ' ')} />
        <AttributeChip label="Positioning" value={attrs.positioning.replace(/_/g, ' ')} />
        <AttributeChip label="Price tier" value={attrs.price_tier} />
        <AttributeChip label="Growth goal" value={attrs.growth_goal.replace(/_/g, ' ')} />
        <AttributeChip label="Core benefit" value={attrs.product_benefit} />
      </div>

      {/* Tone & competitors */}
      {(attrs.tone?.length > 0 || attrs.competitors?.length > 0) && (
        <div className="mt-3 pt-3 border-t border-[var(--border)] flex flex-wrap gap-4">
          {attrs.tone?.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--mist)] mb-1.5">Tone</p>
              <div className="flex flex-wrap gap-1">
                {attrs.tone.map((t) => (
                  <span key={t} className="px-2 py-0.5 rounded-md bg-[var(--linen)] text-[var(--charcoal)] text-xs">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
          {attrs.competitors?.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--mist)] mb-1.5">Competitors</p>
              <div className="flex flex-wrap gap-1">
                {attrs.competitors.slice(0, 4).map((c) => (
                  <span key={c} className="px-2 py-0.5 rounded-md border border-[var(--border)] bg-white text-[var(--smoke)] text-xs">
                    {c}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AttributeChip({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-[var(--mist)] mb-0.5">{label}</p>
      <p className="text-[var(--charcoal)] text-sm font-medium capitalize">{value}</p>
    </div>
  );
}
