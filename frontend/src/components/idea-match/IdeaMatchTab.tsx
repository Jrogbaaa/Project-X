'use client';

import { useState, useRef } from 'react';
import { Search, Lightbulb, ArrowRight } from 'lucide-react';
import { IdeaBrief } from '@/types/ideaMatch';
import { generateIdeaBrief } from '@/lib/ideaMatchApi';
import { BrandProfileCard } from './BrandProfileCard';
import { IdeaCardComponent } from './IdeaCard';

type LoadingStep = 'extracting' | 'selecting' | 'retrieving' | 'generating' | 'ranking' | null;

const EXAMPLE_BRANDS = ['Nike', 'Dove', 'Liquid Death', 'Patagonia', 'Spotify'];

export function IdeaMatchTab() {
  const [brandInput, setBrandInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState<LoadingStep>(null);
  const [brief, setBrief] = useState<IdeaBrief | null>(null);
  const [error, setError] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const startLoadingSteps = () => {
    setLoadingStep('extracting');
    const t1 = setTimeout(() => setLoadingStep('selecting'), 700);
    const t2 = setTimeout(() => setLoadingStep('retrieving'), 1400);
    const t3 = setTimeout(() => setLoadingStep('generating'), 2200);
    const t4 = setTimeout(() => setLoadingStep('ranking'), 5500);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4); };
  };

  const handleSubmit = async (brand: string = brandInput) => {
    const input = brand.trim();
    if (!input || isLoading) return;

    setIsLoading(true);
    setError(null);
    setBrief(null);

    const cleanup = startLoadingSteps();

    try {
      const result = await generateIdeaBrief(input);
      setBrief(result);
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    } finally {
      cleanup();
      setIsLoading(false);
      setLoadingStep(null);
    }
  };

  const handleExample = (brand: string) => {
    setBrandInput(brand);
    handleSubmit(brand);
  };

  return (
    <div className="min-h-[60vh]">
      {/* ── Hero ────────────────────────────────────────────────────── */}
      <section className="pt-14 pb-10 sm:pt-20 sm:pb-14">
        <div className="max-w-4xl mx-auto px-6">
          <div className="mb-10 animate-fade-in">
            <h1 className="font-serif font-[400] text-[3.2rem] sm:text-[4.2rem] lg:text-hero text-[var(--slate)] leading-[1.04] tracking-tight">
              Match a brand
              <br />
              <em className="text-[var(--clay)]" style={{ fontStyle: 'italic' }}>to creative ideas.</em>
            </h1>
            <p className="text-[var(--smoke)] text-base sm:text-[1.05rem] max-w-[520px] leading-relaxed mt-5">
              Enter a brand name. We extract its positioning, select the right creative frameworks, and generate structured campaign ideas grounded in advertising research.
            </p>
          </div>

          {/* Input */}
          <div className="animate-scale-in" style={{ animationDelay: '140ms' }}>
            <div className="relative flex items-center gap-3">
              <div className="relative flex-1">
                <Lightbulb className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--mist)] pointer-events-none" />
                <input
                  ref={inputRef}
                  type="text"
                  value={brandInput}
                  onChange={(e) => setBrandInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                  placeholder="Enter a brand name, e.g. Nike, Dove, Patagonia..."
                  disabled={isLoading}
                  className="w-full pl-11 pr-4 py-3.5 rounded-xl border border-[var(--border)] bg-white text-[var(--slate)] placeholder-[var(--mist)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--clay)]/30 focus:border-[var(--clay)] transition-all disabled:opacity-50"
                />
              </div>
              <button
                onClick={() => handleSubmit()}
                disabled={!brandInput.trim() || isLoading}
                className="flex items-center gap-2 px-5 py-3.5 rounded-xl bg-[var(--clay)] text-white text-sm font-medium hover:bg-[var(--clay-dark)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
              >
                Generate
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Examples */}
          <div className="mt-5 flex flex-wrap items-center gap-2 animate-fade-in" style={{ animationDelay: '240ms' }}>
            <span className="text-xs text-[var(--mist)]">Try:</span>
            {EXAMPLE_BRANDS.map((brand) => (
              <button
                key={brand}
                onClick={() => handleExample(brand)}
                disabled={isLoading}
                className="px-3 py-1.5 rounded-md bg-[var(--parchment)] text-[var(--charcoal)] text-xs border border-[var(--border)] hover:border-[var(--clay)]/40 hover:text-[var(--slate)] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {brand}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Divider */}
      <div className="max-w-6xl mx-auto px-6">
        <div className="h-px bg-[var(--border)]" />
      </div>

      {/* ── Results ─────────────────────────────────────────────────── */}
      <section className="pb-24 pt-10">
        <div className="max-w-6xl mx-auto px-6">

          {/* Loading */}
          {isLoading && (
            <div className="flex justify-center py-24">
              <div className="flex flex-col items-center gap-8">
                <div className="relative w-9 h-9">
                  <div className="absolute inset-0 rounded-full border border-[var(--border)]" />
                  <div className="absolute inset-0 rounded-full border border-t-[var(--clay)] border-r-transparent border-b-transparent border-l-transparent animate-spin" />
                </div>
                <div className="flex flex-col gap-3">
                  <StepIndicator label="Extracting brand attributes..." isActive={loadingStep === 'extracting'} isComplete={['selecting','retrieving','generating','ranking'].includes(loadingStep || '')} />
                  <StepIndicator label="Selecting creative frameworks..." isActive={loadingStep === 'selecting'} isComplete={['retrieving','generating','ranking'].includes(loadingStep || '')} />
                  <StepIndicator label="Retrieving analogous campaigns..." isActive={loadingStep === 'retrieving'} isComplete={['generating','ranking'].includes(loadingStep || '')} />
                  <StepIndicator label="Generating ideas via GPT-5.4..." isActive={loadingStep === 'generating'} isComplete={loadingStep === 'ranking'} />
                  <StepIndicator label="Scoring and ranking..." isActive={loadingStep === 'ranking'} isComplete={false} />
                </div>
              </div>
            </div>
          )}

          {/* Error */}
          {error && !isLoading && (
            <div className="py-12 text-center">
              <p className="text-[var(--mist)] text-sm">{error}</p>
            </div>
          )}

          {/* Brief output */}
          {brief && !isLoading && (
            <div className="animate-fade-in space-y-8" ref={resultsRef}>
              {/* Brand profile */}
              <BrandProfileCard
                attrs={brief.brand_attributes}
                archetype={brief.archetype}
                archetypeRationale={brief.archetype_rationale}
                brandVertical={brief.brand_vertical}
                brandSummary={brief.brand_summary}
              />

              {/* Ideas header */}
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--clay)] font-medium mb-1">
                    Campaign Ideas
                  </p>
                  <h2 className="text-[var(--slate)] text-xl font-semibold">
                    {brief.ideas.length} ideas · ranked by strategic fit
                  </h2>
                </div>
                <div className="text-right text-xs text-[var(--mist)]">
                  <p>{brief.frameworks_selected.length} frameworks applied</p>
                  <p>{brief.retrieved_examples_count} campaigns retrieved</p>
                </div>
              </div>

              {/* Ideas grid */}
              <div className="space-y-4">
                {brief.ideas.map((idea, i) => (
                  <IdeaCardComponent key={i} idea={idea} rank={i + 1} />
                ))}
              </div>

              {/* Bold bet */}
              {brief.bold_bet && (
                <div>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="h-px flex-1 bg-[var(--clay)]/20" />
                    <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--clay)] font-medium">Bold Bet</p>
                    <div className="h-px flex-1 bg-[var(--clay)]/20" />
                  </div>
                  <IdeaCardComponent idea={brief.bold_bet} isBoldBet />
                </div>
              )}

              {/* Reset */}
              <div className="pt-4 border-t border-[var(--border)] flex justify-center">
                <button
                  onClick={() => {
                    setBrief(null);
                    setBrandInput('');
                    setError(null);
                    setTimeout(() => inputRef.current?.focus(), 100);
                  }}
                  className="text-sm text-[var(--mist)] hover:text-[var(--charcoal)] transition-colors"
                >
                  Generate ideas for another brand →
                </button>
              </div>
            </div>
          )}

          {/* Empty state */}
          {!brief && !isLoading && !error && (
            <div className="py-20">
              <div className="max-w-lg mx-auto">
                <div className="flex items-center gap-4 mb-8">
                  <div className="h-px flex-1 bg-[var(--border)]" />
                  <div className="w-1 h-1 rounded-full bg-[var(--border)]" />
                  <div className="h-px flex-1 bg-[var(--border)]" />
                </div>
                <div className="bg-white rounded-xl border border-[var(--border)] p-6 shadow-[var(--shadow-sm)]">
                  <p className="text-[10px] font-medium text-[var(--clay)] uppercase tracking-[0.12em] mb-3">
                    How it works
                  </p>
                  <ul className="space-y-2.5 text-[var(--smoke)] text-sm leading-relaxed">
                    <li className="flex gap-2">
                      <span className="text-[var(--clay)] font-medium shrink-0">1.</span>
                      Enter a brand name — known or unknown, any category
                    </li>
                    <li className="flex gap-2">
                      <span className="text-[var(--clay)] font-medium shrink-0">2.</span>
                      We extract the brand's archetype, positioning, and growth goal
                    </li>
                    <li className="flex gap-2">
                      <span className="text-[var(--clay)] font-medium shrink-0">3.</span>
                      Goldenberg creativity templates are selected based on the goal
                    </li>
                    <li className="flex gap-2">
                      <span className="text-[var(--clay)] font-medium shrink-0">4.</span>
                      Analogous real campaigns are retrieved as creative context
                    </li>
                    <li className="flex gap-2">
                      <span className="text-[var(--clay)] font-medium shrink-0">5.</span>
                      GPT-5.4 generates structured ideas, each traceable to a template
                    </li>
                    <li className="flex gap-2">
                      <span className="text-[var(--clay)] font-medium shrink-0">6.</span>
                      Ideas are scored and ranked by brand fit, originality, and feasibility
                    </li>
                  </ul>
                </div>
                <div className="flex items-center gap-4 mt-8">
                  <div className="h-px flex-1 bg-[var(--border)]" />
                  <div className="w-1 h-1 rounded-full bg-[var(--border)]" />
                  <div className="h-px flex-1 bg-[var(--border)]" />
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

// ── Step indicator ────────────────────────────────────────────────────────────

function StepIndicator({ label, isActive, isComplete }: { label: string; isActive: boolean; isComplete: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div
        className={`w-2 h-2 rounded-full flex-shrink-0 transition-all duration-300 ${
          isComplete
            ? 'bg-[var(--metric-excellent)]'
            : isActive
              ? 'bg-[var(--clay)] animate-pulse'
              : 'bg-[var(--border)]'
        }`}
      />
      <span
        className={`text-sm transition-colors ${
          isComplete
            ? 'text-[var(--metric-excellent)]'
            : isActive
              ? 'text-[var(--slate)]'
              : 'text-[var(--mist)]'
        }`}
      >
        {label}
      </span>
    </div>
  );
}
