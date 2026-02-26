'use client';

import { useState, useCallback, useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Search, ArrowRight, Loader2 } from 'lucide-react';
import { searchInfluencers } from '@/lib/api';
import { SearchResponse, FilterConfig } from '@/types/search';

interface SearchBarProps {
  onResults: (results: SearchResponse) => void;
  filters: FilterConfig;
  onLoadingChange: (loading: boolean) => void;
}

export interface SearchBarRef {
  setQueryAndSearch: (query: string) => void;
}

export const SearchBar = forwardRef<SearchBarRef, SearchBarProps>(
  function SearchBar({ onResults, filters, onLoadingChange }, ref) {
    const [query, setQuery] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [isFocused, setIsFocused] = useState(false);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const resizeTextarea = useCallback(() => {
      const el = textareaRef.current;
      if (!el) return;
      el.style.height = 'auto';
      el.style.height = `${el.scrollHeight}px`;
    }, []);

    useEffect(() => { resizeTextarea(); }, [query, resizeTextarea]);

    const searchMutation = useMutation({
      mutationFn: searchInfluencers,
      onSuccess: (data) => {
        onResults(data);
        setError(null);
        onLoadingChange(false);
      },
      onError: (err: Error) => {
        setError(err.message || 'Error en la búsqueda. Por favor, inténtalo de nuevo.');
        onLoadingChange(false);
      },
      onMutate: () => {
        onLoadingChange(true);
      },
    });

    const executeSearch = useCallback((searchQuery: string) => {
      if (searchQuery.trim().length < 3) {
        setError('Por favor, introduce al menos 3 caracteres');
        return;
      }
      searchMutation.mutate({
        query: searchQuery.trim(),
        filters,
        limit: 20,
      });
    }, [filters, searchMutation]);

    const handleSearch = useCallback(() => {
      executeSearch(query);
    }, [query, executeSearch]);

    useImperativeHandle(ref, () => ({
      setQueryAndSearch: (newQuery: string) => {
        setQuery(newQuery);
        setError(null);
        executeSearch(newQuery);
      },
    }), [executeSearch]);

    return (
      <div className="w-full max-w-3xl mx-auto">

        {/* Search container */}
        <div
          className={`relative bg-dark-secondary rounded-xl border transition-all duration-250 ${
            isFocused
              ? 'border-ember-warm/50 shadow-ember-glow'
              : 'border-dark-border hover:border-dark-border/80'
          }`}
        >
          {/* Search icon */}
          <div className="absolute inset-y-0 left-0 pl-4 flex items-start pt-[1.05rem] pointer-events-none">
            <Search
              className={`h-[1rem] w-[1rem] transition-colors duration-200 ${
                isFocused ? 'text-ember-warm' : 'text-light-tertiary'
              }`}
            />
          </div>

          {/* Textarea */}
          <textarea
            ref={textareaRef}
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
            placeholder="Pega tu brief de marca o describe tu campaña..."
            className="w-full min-h-[58px] pl-11 pr-32 py-[0.95rem] text-sm leading-relaxed
                       bg-transparent text-light-primary rounded-xl focus:outline-none resize-none
                       placeholder:text-light-tertiary/45"
            disabled={searchMutation.isPending}
            style={{ height: '58px', overflow: 'hidden' }}
          />

          {/* Submit button */}
          <button
            onClick={handleSearch}
            disabled={searchMutation.isPending || query.trim().length < 3}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 h-9 px-5
                       bg-ember-warm text-white font-medium text-sm rounded-lg
                       hover:bg-ember-hot
                       disabled:bg-dark-ash disabled:text-light-tertiary disabled:cursor-not-allowed
                       transition-all duration-200 flex items-center gap-1.5
                       shadow-sm"
          >
            {searchMutation.isPending ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span className="hidden sm:inline">Buscando</span>
              </>
            ) : (
              <>
                <span>Buscar</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </>
            )}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="mt-2.5 flex items-center justify-center gap-2 animate-fade-in">
            <div className="w-1 h-1 rounded-full bg-metric-poor" />
            <p className="text-metric-poor text-sm">{error}</p>
          </div>
        )}

        {/* Character hint */}
        {query.length > 0 && query.length < 3 && (
          <p className="mt-2 text-center text-xs text-light-tertiary/70 animate-fade-in">
            {3 - query.length} carácter{3 - query.length > 1 ? 'es' : ''} más
          </p>
        )}
      </div>
    );
  }
);
