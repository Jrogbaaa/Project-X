'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { SearchBar, SearchBarRef } from '@/components/search/SearchBar';
import { FilterPanel } from '@/components/search/FilterPanel';
import { ResultsGrid } from '@/components/results/ResultsGrid';
import { ToastContainer } from '@/components/ui/Toast';
import { SearchResponse, FilterConfig } from '@/types/search';
import { useToast } from '@/hooks/useToast';
import { SlidersHorizontal, Clock, Bookmark } from 'lucide-react';
import Image from 'next/image';

type LoadingStep = 'parsing' | 'searching' | 'ranking' | null;

export default function Home() {
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null);
  const [filters, setFilters] = useState<FilterConfig>({
    min_credibility_score: 70,
    min_spain_audience_pct: 60,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState<LoadingStep>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number>(-1);

  const searchBarRef = useRef<SearchBarRef>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const { toasts, toast, dismiss } = useToast();

  // Auto-scroll to results when search completes
  useEffect(() => {
    if (searchResults && !isLoading && resultsRef.current) {
      const timer = setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [searchResults, isLoading]);

  // Simulate loading steps
  useEffect(() => {
    if (isLoading) {
      setLoadingStep('parsing');
      const timer1 = setTimeout(() => setLoadingStep('searching'), 800);
      const timer2 = setTimeout(() => setLoadingStep('ranking'), 2500);
      return () => {
        clearTimeout(timer1);
        clearTimeout(timer2);
      };
    } else {
      setLoadingStep(null);
    }
  }, [isLoading]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!searchResults || searchResults.results.length === 0) return;
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

    const maxIndex = searchResults.results.length - 1;

    switch (e.key) {
      case 'j':
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, maxIndex));
        break;
      case 'k':
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
        break;
      case 'c':
        if (selectedIndex >= 0 && selectedIndex <= maxIndex) {
          const influencer = searchResults.results[selectedIndex];
          navigator.clipboard.writeText(`@${influencer.raw_data.username}`);
          toast('Usuario copiado', 'success');
        }
        break;
      case 'o':
        if (selectedIndex >= 0 && selectedIndex <= maxIndex) {
          const influencer = searchResults.results[selectedIndex];
          const url = influencer.raw_data.profile_url || `https://instagram.com/${influencer.raw_data.username}`;
          window.open(url, '_blank');
        }
        break;
      case 'm':
        if (selectedIndex >= 0 && selectedIndex <= maxIndex) {
          const influencer = searchResults.results[selectedIndex];
          if (influencer.raw_data.mediakit_url) {
            window.open(influencer.raw_data.mediakit_url, '_blank');
          }
        }
        break;
      case 'Escape':
        setSelectedIndex(-1);
        break;
    }
  }, [searchResults, selectedIndex, toast]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    setSelectedIndex(-1);
  }, [searchResults]);

  const exampleSearches = [
    'Campaña Adidas padel, estilo documental',
    '10 creadores lifestyle para IKEA',
    'Nike running, tono auténtico, 100K-2M seguidores',
  ];

  const handleExampleClick = (example: string) => {
    searchBarRef.current?.setQueryAndSearch(example);
  };

  return (
    <main className="min-h-screen bg-dark-primary">

      {/* ─── Header ─────────────────────────────────────────────── */}
      <header className="relative z-20 border-b border-dark-border/50 bg-dark-primary/95 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">

            {/* Logo */}
            <Image
              src="/look-after-you-logo.png"
              alt="Look After You"
              width={160}
              height={32}
              className="h-7 w-auto object-contain"
              priority
            />

            {/* Nav */}
            <nav className="flex items-center gap-5">
              <button className="flex items-center gap-1.5 text-light-tertiary hover:text-light-secondary transition-colors text-sm group">
                <Clock className="w-3.5 h-3.5 group-hover:text-ember-warm transition-colors" />
                <span className="hidden sm:inline">Historial</span>
              </button>
              <button className="flex items-center gap-1.5 text-light-tertiary hover:text-light-secondary transition-colors text-sm group">
                <Bookmark className="w-3.5 h-3.5 group-hover:text-ember-warm transition-colors" />
                <span className="hidden sm:inline">Guardados</span>
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* ─── Hero ────────────────────────────────────────────────── */}
      <section className="relative pt-14 pb-10 sm:pt-20 sm:pb-14">
        <div className="max-w-4xl mx-auto px-6">

          {/* Editorial headline */}
          <div className="mb-10 animate-fade-in">
            <h1 className="font-serif font-[400] text-[3.2rem] sm:text-[4.2rem] lg:text-hero text-light-primary leading-[1.04] tracking-tight">
              Encuentra
              <br />
              <em className="text-ember-warm" style={{ fontStyle: 'italic' }}>influencers</em>
              <br />
              para tu marca.
            </h1>
            <p
              className="text-light-secondary text-base sm:text-[1.05rem] max-w-[520px] leading-relaxed mt-5 animate-fade-in"
              style={{ animationDelay: '80ms' }}
            >
              Pega tu brief de marca y nuestra IA extrae nicho, afinidad y encaje creativo para encontrar los mejores candidatos.
            </p>
          </div>

          {/* Search Bar */}
          <div className="animate-scale-in" style={{ animationDelay: '140ms' }}>
            <SearchBar
              ref={searchBarRef}
              onResults={setSearchResults}
              filters={filters}
              onLoadingChange={setIsLoading}
            />
          </div>

          {/* Filter toggle + examples */}
          <div
            className="mt-5 flex flex-col sm:flex-row items-start sm:items-center gap-3 animate-fade-in"
            style={{ animationDelay: '240ms' }}
          >
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all border ${
                showFilters
                  ? 'bg-ember-warm/10 text-ember-warm border-ember-warm/30'
                  : 'bg-dark-secondary text-light-secondary border-dark-border hover:text-light-primary hover:border-ember-warm/20'
              }`}
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              Filtros
            </button>

            <div className="hidden sm:block w-px h-5 bg-dark-border/60" />

            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-light-tertiary/70">Prueba:</span>
              {exampleSearches.map((example, i) => (
                <button
                  key={i}
                  onClick={() => handleExampleClick(example)}
                  disabled={isLoading}
                  className="px-3 py-1.5 rounded-md bg-dark-secondary text-light-secondary text-xs border border-dark-border/60 hover:border-ember-warm/30 hover:text-light-primary transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  aria-label={`Buscar: ${example}`}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>

          {/* Filter panel */}
          {showFilters && (
            <div className="mt-5 animate-slide-down">
              <FilterPanel filters={filters} onChange={setFilters} />
            </div>
          )}
        </div>
      </section>

      {/* Divider */}
      <div className="max-w-6xl mx-auto px-6">
        <div className="h-px bg-dark-border/50" />
      </div>

      {/* ─── Results ─────────────────────────────────────────────── */}
      <section className="pb-24 pt-10">
        <div className="max-w-6xl mx-auto px-6">

          {/* Loading */}
          {isLoading && (
            <div className="flex justify-center py-24">
              <div className="flex flex-col items-center gap-8">
                {/* Refined spinner */}
                <div className="relative w-9 h-9">
                  <div className="absolute inset-0 rounded-full border border-dark-border/50" />
                  <div className="absolute inset-0 rounded-full border border-t-ember-warm border-r-transparent border-b-transparent border-l-transparent animate-spin" />
                </div>

                {/* Steps */}
                <div className="flex flex-col gap-3">
                  <LoadingStepIndicator
                    step="parsing"
                    label="Analizando brief..."
                    isActive={loadingStep === 'parsing'}
                    isComplete={loadingStep === 'searching' || loadingStep === 'ranking'}
                  />
                  <LoadingStepIndicator
                    step="searching"
                    label="Buscando en PrimeTag..."
                    isActive={loadingStep === 'searching'}
                    isComplete={loadingStep === 'ranking'}
                  />
                  <LoadingStepIndicator
                    step="ranking"
                    label="Clasificando resultados..."
                    isActive={loadingStep === 'ranking'}
                    isComplete={false}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Results grid */}
          {searchResults && !isLoading && (
            <div className="animate-fade-in" ref={resultsRef}>
              <ResultsGrid
                searchResponse={searchResults}
                selectedIndex={selectedIndex}
                onToast={(message) => toast(message, 'success')}
              />
            </div>
          )}

          {/* Empty state */}
          {!searchResults && !isLoading && (
            <div className="py-20">
              <div className="max-w-lg mx-auto">
                {/* Decorative rule */}
                <div className="flex items-center gap-4 mb-8">
                  <div className="h-px flex-1 bg-dark-border/40" />
                  <div className="w-1 h-1 rounded-full bg-dark-border" />
                  <div className="h-px flex-1 bg-dark-border/40" />
                </div>

                {/* Example brief card */}
                <div className="bg-dark-secondary rounded-xl border border-dark-border/60 p-6 shadow-card">
                  <p className="text-[10px] font-medium text-ember-warm uppercase tracking-[0.12em] mb-3">
                    Ejemplo de brief
                  </p>
                  <p className="text-light-secondary text-sm leading-relaxed italic font-serif">
                    &quot;Buscar 5 influencers españoles para campaña de Adidas padel. Concepto creativo: serie &apos;Rising Stars&apos; con atletas emergentes en momentos auténticos de entrenamiento, estilo documental. Preferir influencers mid-tier (100K–2M seguidores).&quot;
                  </p>
                </div>

                <div className="flex items-center gap-4 mt-8">
                  <div className="h-px flex-1 bg-dark-border/40" />
                  <div className="w-1 h-1 rounded-full bg-dark-border" />
                  <div className="h-px flex-1 bg-dark-border/40" />
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ─── Footer ──────────────────────────────────────────────── */}
      <footer className="border-t border-dark-border/40 py-5">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex items-center justify-between">
            <p className="text-xs text-light-tertiary/70">
              Impulsado por PrimeTag API
            </p>
            <p className="text-xs text-light-tertiary/60 hidden sm:flex items-center gap-2">
              <kbd className="px-1.5 py-0.5 rounded border border-dark-border bg-dark-secondary text-[10px] font-mono text-light-secondary">j</kbd>
              <kbd className="px-1.5 py-0.5 rounded border border-dark-border bg-dark-secondary text-[10px] font-mono text-light-secondary">k</kbd>
              <span>navegar</span>
              <span className="text-dark-border">·</span>
              <kbd className="px-1.5 py-0.5 rounded border border-dark-border bg-dark-secondary text-[10px] font-mono text-light-secondary">c</kbd>
              <span>copiar</span>
              <span className="text-dark-border">·</span>
              <kbd className="px-1.5 py-0.5 rounded border border-dark-border bg-dark-secondary text-[10px] font-mono text-light-secondary">o</kbd>
              <span>abrir</span>
            </p>
          </div>
        </div>
      </footer>

      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </main>
  );
}

// ─── Loading Step Indicator ───────────────────────────────────

interface LoadingStepIndicatorProps {
  step: string;
  label: string;
  isActive: boolean;
  isComplete: boolean;
}

function LoadingStepIndicator({ label, isActive, isComplete }: LoadingStepIndicatorProps) {
  return (
    <div className="flex items-center gap-3">
      <div
        className={`w-2 h-2 rounded-full flex-shrink-0 transition-all duration-300 ${
          isComplete
            ? 'bg-metric-excellent'
            : isActive
              ? 'bg-ember-warm animate-pulse-subtle'
              : 'bg-dark-border'
        }`}
      />
      <span
        className={`text-sm transition-colors ${
          isComplete
            ? 'text-metric-excellent'
            : isActive
              ? 'text-light-primary'
              : 'text-light-tertiary'
        }`}
      >
        {label}
      </span>
    </div>
  );
}
