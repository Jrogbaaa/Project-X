'use client';

import { useState } from 'react';
import { SearchBar } from '@/components/search/SearchBar';
import { FilterPanel } from '@/components/search/FilterPanel';
import { ResultsGrid } from '@/components/results/ResultsGrid';
import { SearchResponse, FilterConfig } from '@/types/search';
import { Sparkles, Clock, Bookmark } from 'lucide-react';

export default function Home() {
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null);
  const [filters, setFilters] = useState<FilterConfig>({
    min_credibility_score: 70,
    min_spain_audience_pct: 60,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const exampleSearches = [
    'Adidas padel campaign, documentary style',
    '10 lifestyle creators for IKEA',
    'Nike running, authentic tone, 100K-2M followers',
  ];

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
                  className="px-3 py-1.5 rounded-full bg-dark-secondary/50 text-light-secondary hover:text-accent-gold hover:bg-dark-secondary transition-all text-xs border border-dark-border/50 hover:border-accent-gold/30"
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
          {/* Loading State */}
          {isLoading && (
            <div className="flex justify-center py-16">
              <div className="flex flex-col items-center gap-4">
                <div className="relative">
                  <div className="w-12 h-12 rounded-full border-2 border-dark-border" />
                  <div className="absolute inset-0 w-12 h-12 rounded-full border-2 border-accent-gold border-t-transparent animate-spin" />
                </div>
                <p className="text-light-secondary text-sm">Discovering influencers...</p>
              </div>
            </div>
          )}

          {/* Results */}
          {searchResults && !isLoading && (
            <div className="animate-fade-in">
              <ResultsGrid searchResponse={searchResults} />
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
          <p className="text-center text-xs text-light-tertiary">
            Powered by PrimeTag API
          </p>
        </div>
      </footer>
    </main>
  );
}
