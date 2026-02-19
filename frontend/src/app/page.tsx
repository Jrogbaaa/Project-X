'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { SearchBar, SearchBarRef } from '@/components/search/SearchBar';
import { FilterPanel } from '@/components/search/FilterPanel';
import { ResultsGrid } from '@/components/results/ResultsGrid';
import { ToastContainer } from '@/components/ui/Toast';
import { SearchResponse, FilterConfig } from '@/types/search';
import { useToast } from '@/hooks/useToast';
import { Sparkles, Clock, Bookmark } from 'lucide-react';

// Loading step type
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
      // Small delay to ensure render is complete
      const timer = setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [searchResults, isLoading]);

  // Simulate loading steps (in real implementation, these would come from the API)
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
    
    // Don't intercept if typing in an input
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

    const maxIndex = searchResults.results.length - 1;

    switch (e.key) {
      case 'j': // Next
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, maxIndex));
        break;
      case 'k': // Previous
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
        break;
      case 'c': // Copy username
        if (selectedIndex >= 0 && selectedIndex <= maxIndex) {
          const influencer = searchResults.results[selectedIndex];
          navigator.clipboard.writeText(`@${influencer.raw_data.username}`);
          toast('Usuario copiado', 'success');
        }
        break;
      case 'o': // Open profile
        if (selectedIndex >= 0 && selectedIndex <= maxIndex) {
          const influencer = searchResults.results[selectedIndex];
          const url = influencer.raw_data.profile_url || `https://instagram.com/${influencer.raw_data.username}`;
          window.open(url, '_blank');
        }
        break;
      case 'm': // Open MediaKit
        if (selectedIndex >= 0 && selectedIndex <= maxIndex) {
          const influencer = searchResults.results[selectedIndex];
          if (influencer.raw_data.mediakit_url) {
            window.open(influencer.raw_data.mediakit_url, '_blank');
          }
        }
        break;
      case 'Escape': // Clear selection
        setSelectedIndex(-1);
        break;
    }
  }, [searchResults, selectedIndex, toast]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Reset selection when results change
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
      {/* Ambient Background Glow - Ember theme */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[700px] bg-gradient-radial from-ember-hot/[0.025] via-ember-core/[0.015] to-transparent" />
        <div className="absolute top-1/3 right-0 w-[500px] h-[500px] bg-gradient-radial from-ember-core/[0.02] to-transparent opacity-50" />
      </div>

      {/* Header */}
      <header className="relative z-20 border-b border-dark-border/40 bg-dark-primary/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-ember-hot/20 to-ember-core/10 flex items-center justify-center border border-ember-core/20">
                <Sparkles className="w-4 h-4 text-ember-warm" />
              </div>
              <span className="font-serif text-lg text-light-primary tracking-tight">
                Descubrimiento de Influencers
              </span>
            </div>

            {/* Nav Actions */}
            <div className="flex items-center gap-6">
              <button className="flex items-center gap-2 text-light-secondary hover:text-ember-glow transition-colors text-sm group">
                <Clock className="w-4 h-4 group-hover:text-ember-core transition-colors" />
                <span className="hidden sm:inline">Historial</span>
              </button>
              <button className="flex items-center gap-2 text-light-secondary hover:text-ember-glow transition-colors text-sm group">
                <Bookmark className="w-4 h-4 group-hover:text-ember-core transition-colors" />
                <span className="hidden sm:inline">Guardados</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative z-10 pt-16 pb-8 sm:pt-24 sm:pb-12">
        <div className="max-w-4xl mx-auto px-6 text-center">
          {/* Headline */}
          <h1 className="font-serif text-4xl sm:text-5xl lg:text-hero text-gradient mb-4 animate-fade-in tracking-tight">
            Descubre
          </h1>
          <p className="text-light-secondary text-lg sm:text-xl mb-4 max-w-2xl mx-auto animate-fade-in"
             style={{ animationDelay: '100ms' }}>
            Pega tu brief de marca y encuentra influencers perfectamente alineados
          </p>
          <p className="text-light-tertiary text-sm mb-10 max-w-xl mx-auto animate-fade-in"
             style={{ animationDelay: '150ms' }}>
            Incluye el nombre de la marca y los detalles de la campaña — nuestra IA encuentra influencers basándose en su nicho, afinidad de marca y encaje creativo.
          </p>

          {/* Search Bar */}
          <div className="animate-scale-in" style={{ animationDelay: '200ms' }}>
            <SearchBar
              ref={searchBarRef}
              onResults={setSearchResults}
              filters={filters}
              onLoadingChange={setIsLoading}
            />
          </div>

          {/* Filter Toggle & Examples */}
          <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-4 animate-fade-in"
               style={{ animationDelay: '300ms' }}>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all
                ${showFilters
                  ? 'bg-ember-core/15 text-ember-warm border border-ember-core/30 shadow-sm shadow-ember-core/10'
                  : 'bg-dark-secondary text-light-secondary hover:text-light-primary border border-dark-border hover:border-ember-core/30'
                }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
              Filtros
            </button>

            <div className="hidden sm:block w-px h-4 bg-dark-border/50" />

            <div className="flex items-center gap-2 text-sm text-light-tertiary">
              <span>Prueba:</span>
              {exampleSearches.map((example, i) => (
                <button
                  key={i}
                  onClick={() => handleExampleClick(example)}
                  disabled={isLoading}
                  className="px-3 py-1.5 rounded-full bg-dark-secondary/60 text-light-secondary hover:text-ember-glow hover:bg-dark-ash/50 transition-all text-xs border border-dark-border/40 hover:border-ember-core/25 disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label={`Search for: ${example}`}
                  tabIndex={0}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>

          {/* Filter Panel */}
          {showFilters && (
            <div className="mt-6 animate-slide-down">
              <FilterPanel filters={filters} onChange={setFilters} />
            </div>
          )}
        </div>
      </section>

      {/* Results Section */}
      <section className="relative z-10 pb-16">
        <div className="max-w-6xl mx-auto px-6">
          {/* Enhanced Loading State */}
          {isLoading && (
            <div className="flex justify-center py-16">
              <div className="flex flex-col items-center gap-6">
                <div className="relative">
                  <div className="w-12 h-12 rounded-full border-2 border-dark-border/50" />
                  <div className="absolute inset-0 w-12 h-12 rounded-full border-2 border-ember-core border-t-transparent animate-spin" />
                  <div className="absolute inset-2 w-8 h-8 rounded-full bg-ember-core/10 animate-pulse" />
                </div>
                
                {/* Loading Steps */}
                <div className="flex flex-col gap-2">
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

          {/* Results */}
          {searchResults && !isLoading && (
            <div className="animate-fade-in" ref={resultsRef}>
              <ResultsGrid 
                searchResponse={searchResults} 
                selectedIndex={selectedIndex}
                onToast={(message) => toast(message, 'success')}
              />
            </div>
          )}

          {/* Empty State */}
          {!searchResults && !isLoading && (
            <div className="text-center py-16">
              <div className="max-w-lg mx-auto">
                <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-dark-secondary to-dark-tertiary border border-dark-border/50 flex items-center justify-center shadow-lg shadow-black/20">
                  <Sparkles className="w-8 h-8 text-ember-core/60" />
                </div>
                <h3 className="font-serif text-xl text-light-primary mb-2">
                  Listo para descubrir
                </h3>
                <p className="text-light-secondary text-sm leading-relaxed mb-6">
                  Pega tu brief de marca arriba. Nuestra IA extrae el contexto de marca, conceptos creativos y requisitos de campaña para encontrar los influencers más alineados.
                </p>
                <div className="bg-dark-secondary/60 rounded-xl p-4 text-left border border-dark-border/40 shadow-inner shadow-black/10">
                  <p className="text-xs text-ember-glow/80 mb-2 uppercase tracking-wider font-medium">Ejemplo de brief:</p>
                  <p className="text-sm text-light-secondary italic leading-relaxed">
                    &quot;Buscar 5 influencers españoles para campaña de Adidas padel. Concepto creativo: serie &apos;Rising Stars&apos; con atletas emergentes en momentos auténticos de entrenamiento, estilo documental. Preferir influencers mid-tier (100K-2M seguidores).&quot;
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-dark-border/30 py-6 bg-dark-primary/50">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex items-center justify-between">
            <p className="text-xs text-light-tertiary">
              Impulsado por PrimeTag API
            </p>
            <p className="text-xs text-light-tertiary hidden sm:block">
              <kbd className="px-1.5 py-0.5 rounded bg-dark-secondary/80 border border-dark-border/50 text-[10px] font-mono text-light-secondary">j</kbd>
              <kbd className="px-1.5 py-0.5 rounded bg-dark-secondary/80 border border-dark-border/50 text-[10px] font-mono text-light-secondary ml-1">k</kbd>
              <span className="ml-2">navegar</span>
              <span className="mx-2 text-dark-border">|</span>
              <kbd className="px-1.5 py-0.5 rounded bg-dark-secondary/80 border border-dark-border/50 text-[10px] font-mono text-light-secondary">c</kbd>
              <span className="ml-2">copiar</span>
              <span className="mx-2 text-dark-border">|</span>
              <kbd className="px-1.5 py-0.5 rounded bg-dark-secondary/80 border border-dark-border/50 text-[10px] font-mono text-light-secondary">o</kbd>
              <span className="ml-2">abrir</span>
            </p>
          </div>
        </div>
      </footer>

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </main>
  );
}

// Loading Step Indicator Component
interface LoadingStepIndicatorProps {
  step: string;
  label: string;
  isActive: boolean;
  isComplete: boolean;
}

function LoadingStepIndicator({ label, isActive, isComplete }: LoadingStepIndicatorProps) {
  return (
    <div className="flex items-center gap-3">
      <div className={`w-2.5 h-2.5 rounded-full transition-all duration-300 ${
        isComplete
          ? 'bg-metric-excellent shadow-sm shadow-metric-excellent/50'
          : isActive
            ? 'bg-ember-core animate-pulse-subtle shadow-sm shadow-ember-core/50'
            : 'bg-dark-border/60'
      }`} />
      <span className={`text-sm transition-colors ${
        isComplete
          ? 'text-metric-excellent'
          : isActive
            ? 'text-light-primary'
            : 'text-light-tertiary'
      }`}>
        {label}
      </span>
    </div>
  );
}
