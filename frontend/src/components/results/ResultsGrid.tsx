'use client';

import { useState } from 'react';
import { Download, FileSpreadsheet, Bookmark, CheckCircle, Tag, Sparkles } from 'lucide-react';
import { SearchResponse } from '@/types/search';
import { InfluencerCard } from './InfluencerCard';
import { downloadExport, saveSearch } from '@/lib/api';

interface ResultsGridProps {
  searchResponse: SearchResponse;
}

export function ResultsGrid({ searchResponse }: ResultsGridProps) {
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [isExporting, setIsExporting] = useState<'csv' | 'excel' | null>(null);

  const handleExport = async (format: 'csv' | 'excel') => {
    setIsExporting(format);
    try {
      await downloadExport(searchResponse.search_id, format);
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setIsExporting(null);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const name = `Search: ${searchResponse.query.substring(0, 50)}`;
      await saveSearch(searchResponse.search_id, name);
      setIsSaved(true);
    } catch (error) {
      console.error('Save failed:', error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Results Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h2 className="font-serif text-xl text-light-primary">Results</h2>
            <div className="h-px flex-1 bg-dark-border max-w-[100px]" />
          </div>
          <p className="text-sm text-light-tertiary">
            <span className="font-mono text-light-secondary">{searchResponse.total_candidates}</span> candidates found,{' '}
            <span className="font-mono text-light-secondary">{searchResponse.total_after_filter}</span> passed filters,{' '}
            showing top <span className="font-mono text-accent-gold">{searchResponse.results.length}</span>
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleExport('csv')}
            disabled={isExporting !== null}
            className="flex items-center gap-2 px-3 py-2 text-xs font-medium
                       text-light-secondary bg-dark-secondary border border-dark-border rounded-lg
                       hover:border-accent-gold/30 hover:text-light-primary
                       disabled:opacity-50 transition-all"
          >
            <Download className="h-3.5 w-3.5" />
            {isExporting === 'csv' ? 'Exporting...' : 'CSV'}
          </button>

          <button
            onClick={() => handleExport('excel')}
            disabled={isExporting !== null}
            className="flex items-center gap-2 px-3 py-2 text-xs font-medium
                       text-light-secondary bg-dark-secondary border border-dark-border rounded-lg
                       hover:border-accent-gold/30 hover:text-light-primary
                       disabled:opacity-50 transition-all"
          >
            <FileSpreadsheet className="h-3.5 w-3.5" />
            {isExporting === 'excel' ? 'Exporting...' : 'Excel'}
          </button>

          <button
            onClick={handleSave}
            disabled={isSaving || isSaved}
            className={`flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg transition-all ${
              isSaved
                ? 'text-metric-excellent bg-metric-excellent/10 border border-metric-excellent/30'
                : 'text-accent-gold bg-accent-gold/10 border border-accent-gold/30 hover:bg-accent-gold/20'
            } disabled:opacity-50`}
          >
            {isSaved ? (
              <>
                <CheckCircle className="h-3.5 w-3.5" />
                Saved
              </>
            ) : (
              <>
                <Bookmark className="h-3.5 w-3.5" />
                {isSaving ? 'Saving...' : 'Save'}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Parsed Query Info */}
      {searchResponse.parsed_query.brand_name && (
        <div className="glass rounded-lg border border-accent-gold/20 p-4">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent-gold/10 flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-4 h-4 text-accent-gold" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className="text-sm text-light-secondary">Detected brand:</span>
                <span className="px-2 py-0.5 rounded-full bg-accent-gold/10 text-accent-gold text-xs font-medium">
                  {searchResponse.parsed_query.brand_name}
                </span>
                {searchResponse.parsed_query.brand_category && (
                  <span className="px-2 py-0.5 rounded-full bg-dark-tertiary text-light-secondary text-xs">
                    {searchResponse.parsed_query.brand_category.replace(/_/g, ' ')}
                  </span>
                )}
              </div>
              {searchResponse.parsed_query.content_themes.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <Tag className="w-3 h-3 text-light-tertiary" />
                  {searchResponse.parsed_query.content_themes.slice(0, 5).map((theme, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded-full bg-dark-tertiary text-light-tertiary text-xs"
                    >
                      {theme.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Results Grid */}
      {searchResponse.results.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1">
          {searchResponse.results.map((result, index) => (
            <InfluencerCard
              key={result.influencer_id}
              influencer={result}
              index={index}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-16">
          <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-dark-secondary border border-dark-border flex items-center justify-center">
            <Sparkles className="w-8 h-8 text-light-tertiary" />
          </div>
          <h3 className="font-serif text-xl text-light-primary mb-2">
            No matches found
          </h3>
          <p className="text-light-secondary text-sm max-w-md mx-auto">
            No influencers matched your criteria. Try adjusting your filters or broadening your search query.
          </p>
        </div>
      )}
    </div>
  );
}
