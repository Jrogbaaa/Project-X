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
          toast('Username copied', 'success');
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
    'Adidas padel campaign, documentary style',
    '10 lifestyle creators for IKEA',
    'Nike running, authentic tone, 100K-2M followers',
  ];

  const handleExampleClick = (example: string) => {
    searchBarRef.current?.setQueryAndSearch(example);
  };

  return (
    <main className="min-h-screen bg-dark-primary">
      {/* Ambient Background Glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-gradient-radial from-accent-gold/[0.03] via-transparent to-transparent" />
      </div>

      {/* Header */}
      <header className="relative z-20 border-b border-dark-border/50">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-accent-gold/10 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-accent-gold" />
              </div>
              <span className="font-serif text-lg text-light-primary tracking-tight">
                Influencer Discovery
              </span>
            </div>

            {/* Nav Actions */}
            <div className="flex items-center gap-6">
              <button className="flex items-center gap-2 text-light-secondary hover:text-light-primary transition-colors text-sm">
                <Clock className="w-4 h-4" />
                <span className="hidden sm:inline">History</span>
              </button>
              <button className="flex items-center gap-2 text-light-secondary hover:text-light-primary transition-colors text-sm">
                <Bookmark className="w-4 h-4" />
                <span className="hidden sm:inline">Saved</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative z-10 pt-16 pb-8 sm:pt-24 sm:pb-12">
        <div className="max-w-4xl mx-auto px-6 text-center">
          {/* Headline */}
          <h1 className="font-serif text-4xl sm:text-5xl lg:text-hero text-light-primary mb-4 animate-fade-in">
            Discover
          </h1>
          <p className="text-light-secondary text-lg sm:text-xl mb-4 max-w-2xl mx-auto animate-fade-in"
             style={{ animationDelay: '100ms' }}>
            Paste your brand brief and find perfectly matched influencers
          </p>
          <p className="text-light-tertiary text-sm mb-10 max-w-xl mx-auto animate-fade-in"
             style={{ animationDelay: '150ms' }}>
            Include brand name, creative concept, tone, and target audience — our AI extracts everything and scores influencers on brand affinity, creative fit, and niche match.
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
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
                ${showFilters
                  ? 'bg-accent-gold/20 text-accent-gold border border-accent-gold/30'
                  : 'bg-dark-secondary text-light-secondary hover:text-light-primary border border-dark-border hover:border-accent-gold/30'
                }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
              Filters
            </button>

            <div className="hidden sm:block w-px h-4 bg-dark-border" />

            <div className="flex items-center gap-2 text-sm text-light-tertiary">
              <span>Try:</span>
              {exampleSearches.map((example, i) => (
                <button
                  key={i}
                  onClick={() => handleExampleClick(example)}
                  disabled={isLoading}
                  className="px-3 py-1.5 rounded-full bg-dark-secondary/50 text-light-secondary hover:text-accent-gold hover:bg-dark-secondary transition-all text-xs border border-dark-border/50 hover:border-accent-gold/30 disabled:opacity-50 disabled:cursor-not-allowed"
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
                  <div className="w-12 h-12 rounded-full border-2 border-dark-border" />
                  <div className="absolute inset-0 w-12 h-12 rounded-full border-2 border-accent-gold border-t-transparent animate-spin" />
                </div>
                
                {/* Loading Steps */}
                <div className="flex flex-col gap-2">
                  <LoadingStepIndicator 
                    step="parsing" 
                    label="Parsing brief..." 
                    isActive={loadingStep === 'parsing'} 
                    isComplete={loadingStep === 'searching' || loadingStep === 'ranking'} 
                  />
                  <LoadingStepIndicator 
                    step="searching" 
                    label="Searching PrimeTag..." 
                    isActive={loadingStep === 'searching'} 
                    isComplete={loadingStep === 'ranking'} 
                  />
                  <LoadingStepIndicator 
                    step="ranking" 
                    label="Ranking results..." 
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
                <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-dark-secondary border border-dark-border flex items-center justify-center">
                  <Sparkles className="w-8 h-8 text-accent-gold/50" />
                </div>
                <h3 className="font-serif text-xl text-light-primary mb-2">
                  Ready to discover
                </h3>
                <p className="text-light-secondary text-sm leading-relaxed mb-6">
                  Paste your brand brief above. Our AI extracts brand context, creative concepts, and campaign requirements to find the best-matched influencers.
                </p>
                <div className="bg-dark-secondary/50 rounded-xl p-4 text-left border border-dark-border/50">
                  <p className="text-xs text-light-tertiary mb-2 uppercase tracking-wider">Example brief:</p>
                  <p className="text-sm text-light-secondary italic">
                    &quot;Find 5 Spanish influencers for Adidas padel campaign. Creative concept: &apos;Rising Stars&apos; series featuring up-and-coming athletes in authentic training moments, documentary style. Prefer mid-tier influencers (100K-2M followers).&quot;
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-dark-border/50 py-6">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex items-center justify-between">
            <p className="text-xs text-light-tertiary">
              Powered by PrimeTag API
            </p>
            <p className="text-xs text-light-tertiary hidden sm:block">
              <kbd className="px-1.5 py-0.5 rounded bg-dark-secondary border border-dark-border text-[10px] font-mono">j</kbd>
              <kbd className="px-1.5 py-0.5 rounded bg-dark-secondary border border-dark-border text-[10px] font-mono ml-1">k</kbd>
              <span className="ml-2">navigate</span>
              <span className="mx-2">|</span>
              <kbd className="px-1.5 py-0.5 rounded bg-dark-secondary border border-dark-border text-[10px] font-mono">c</kbd>
              <span className="ml-2">copy</span>
              <span className="mx-2">|</span>
              <kbd className="px-1.5 py-0.5 rounded bg-dark-secondary border border-dark-border text-[10px] font-mono">o</kbd>
              <span className="ml-2">open</span>
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
      <div className={`w-2 h-2 rounded-full transition-all duration-300 ${
        isComplete 
          ? 'bg-metric-excellent' 
          : isActive 
            ? 'bg-accent-gold animate-pulse-subtle' 
            : 'bg-dark-border'
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
