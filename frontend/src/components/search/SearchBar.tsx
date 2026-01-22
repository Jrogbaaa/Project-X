'use client';

import { useState, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Search, ArrowRight, Loader2 } from 'lucide-react';
import { searchInfluencers } from '@/lib/api';
import { SearchResponse, FilterConfig } from '@/types/search';

interface SearchBarProps {
  onResults: (results: SearchResponse) => void;
  filters: FilterConfig;
  onLoadingChange: (loading: boolean) => void;
}

export function SearchBar({ onResults, filters, onLoadingChange }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isFocused, setIsFocused] = useState(false);

  const searchMutation = useMutation({
    mutationFn: searchInfluencers,
    onSuccess: (data) => {
      onResults(data);
      setError(null);
      onLoadingChange(false);
    },
    onError: (err: Error) => {
      setError(err.message || 'Search failed. Please try again.');
      onLoadingChange(false);
    },
    onMutate: () => {
      onLoadingChange(true);
    },
  });

  const handleSearch = useCallback(() => {
    if (query.trim().length < 3) {
      setError('Please enter at least 3 characters');
      return;
    }

    searchMutation.mutate({
      query: query.trim(),
      filters,
      limit: 10,
    });
  }, [query, filters, searchMutation]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto">
      {/* Search Container with Glow Effect */}
      <div
        className={`relative transition-all duration-500 ${
          isFocused ? 'glow-gold-intense' : ''
        }`}
      >
        {/* Gradient Border */}
        <div
          className={`absolute -inset-[1px] rounded-2xl bg-gradient-to-r transition-opacity duration-500 ${
            isFocused
              ? 'from-accent-gold/60 via-accent-gold-light/40 to-accent-gold/60 opacity-100'
              : 'from-dark-border via-dark-border to-dark-border opacity-100'
          }`}
        />

        {/* Input Container */}
        <div className="relative bg-dark-secondary rounded-2xl">
          {/* Search Icon */}
          <div className="absolute inset-y-0 left-0 pl-5 flex items-center pointer-events-none">
            <Search
              className={`h-5 w-5 transition-colors duration-300 ${
                isFocused ? 'text-accent-gold' : 'text-light-tertiary'
              }`}
            />
          </div>

          {/* Input Field - Supports pasting full briefs */}
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSearch();
              }
            }}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder="Paste your brand brief or describe your campaign..."
            className="w-full min-h-[60px] max-h-[200px] pl-14 pr-32 py-4 text-base bg-transparent text-light-primary
                       rounded-2xl focus:outline-none transition-all duration-300 resize-none
                       placeholder:text-light-tertiary/60"
            disabled={searchMutation.isPending}
            rows={1}
            style={{ height: query.length > 100 ? 'auto' : '60px' }}
          />

          {/* Search Button */}
          <button
            onClick={handleSearch}
            disabled={searchMutation.isPending || query.trim().length < 3}
            className="absolute right-2 top-1/2 -translate-y-1/2 h-[44px] px-6
                       bg-accent-gold text-dark-primary font-semibold rounded-xl
                       hover:bg-accent-gold-light
                       disabled:bg-dark-tertiary disabled:text-light-tertiary disabled:cursor-not-allowed
                       transition-all duration-300 flex items-center gap-2
                       shadow-lg shadow-accent-gold/20 hover:shadow-accent-gold/30
                       disabled:shadow-none"
          >
            {searchMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="hidden sm:inline">Searching</span>
              </>
            ) : (
              <>
                <span>Search</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mt-3 flex items-center justify-center gap-2 animate-fade-in">
          <div className="w-1.5 h-1.5 rounded-full bg-metric-poor" />
          <p className="text-metric-poor text-sm">{error}</p>
        </div>
      )}

      {/* Character Count Hint */}
      {query.length > 0 && query.length < 3 && (
        <p className="mt-2 text-center text-xs text-light-tertiary animate-fade-in">
          {3 - query.length} more character{3 - query.length > 1 ? 's' : ''} needed
        </p>
      )}
    </div>
  );
}
