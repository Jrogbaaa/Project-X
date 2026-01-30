'use client';

import { useState, forwardRef } from 'react';
import { Download, FileSpreadsheet, Bookmark, CheckCircle, Tag, Sparkles, LayoutGrid, List, ShieldCheck } from 'lucide-react';
import { SearchResponse } from '@/types/search';
import { InfluencerCard } from './InfluencerCard';
import { InfluencerRow } from './InfluencerRow';
import { downloadExport, saveSearch } from '@/lib/api';
import { cn } from '@/lib/utils';

type ViewMode = 'cards' | 'list';

interface ResultsGridProps {
  searchResponse: SearchResponse;
  selectedIndex?: number;
  onToast?: (message: string) => void;
}

export const ResultsGrid = forwardRef<HTMLDivElement, ResultsGridProps>(function ResultsGrid(
  { searchResponse, selectedIndex, onToast },
  ref
) {
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [isExporting, setIsExporting] = useState<'csv' | 'excel' | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('cards');

  const handleExport = async (format: 'csv' | 'excel') => {
    setIsExporting(format);
    onToast?.(`Exportando ${format.toUpperCase()}...`);
    try {
      await downloadExport(searchResponse.search_id, format);
      onToast?.(`${format.toUpperCase()} descargado`);
    } catch (error) {
      console.error('Export failed:', error);
      onToast?.('Error en la exportación');
    } finally {
      setIsExporting(null);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const name = `Búsqueda: ${searchResponse.query.substring(0, 50)}`;
      await saveSearch(searchResponse.search_id, name);
      setIsSaved(true);
      onToast?.('Búsqueda guardada');
    } catch (error) {
      console.error('Save failed:', error);
      onToast?.('Error al guardar');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCopy = (message: string) => {
    onToast?.(message);
  };

  return (
    <div className="space-y-6" ref={ref}>
      {/* Results Header - Sticky */}
      <div className="sticky top-0 z-20 -mx-6 px-6 py-4 bg-dark-primary/95 backdrop-blur-md border-b border-dark-border/30">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h2 className="font-serif text-xl text-light-primary">Resultados</h2>
              <div className="h-px flex-1 bg-dark-border max-w-[100px]" />
            </div>
            <p className="text-sm text-light-tertiary">
              <span className="font-mono text-light-secondary">{searchResponse.total_candidates}</span> candidatos encontrados,{' '}
              <span className="font-mono text-light-secondary">{searchResponse.total_after_filter}</span> pasaron filtros,{' '}
              mostrando top <span className="font-mono text-accent-gold">{searchResponse.results.length}</span>
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            {/* View Mode Toggle */}
            <div className="flex items-center rounded-lg border border-dark-border p-0.5 mr-2">
              <button
                onClick={() => setViewMode('cards')}
                className={cn(
                  'p-1.5 rounded-md transition-all',
                  viewMode === 'cards'
                    ? 'bg-accent-gold/20 text-accent-gold'
                    : 'text-light-tertiary hover:text-light-secondary'
                )}
                aria-label="Card view"
                title="Card view"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={cn(
                  'p-1.5 rounded-md transition-all',
                  viewMode === 'list'
                    ? 'bg-accent-gold/20 text-accent-gold'
                    : 'text-light-tertiary hover:text-light-secondary'
                )}
                aria-label="List view"
                title="List view"
              >
                <List className="w-4 h-4" />
              </button>
            </div>
          <button
            onClick={() => handleExport('csv')}
            disabled={isExporting !== null}
            className="flex items-center gap-2 px-3 py-2 text-xs font-medium
                       text-light-secondary bg-dark-secondary border border-dark-border rounded-lg
                       hover:border-accent-gold/30 hover:text-light-primary
                       disabled:opacity-50 transition-all"
          >
            <Download className="h-3.5 w-3.5" />
            {isExporting === 'csv' ? 'Exportando...' : 'CSV'}
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
            {isExporting === 'excel' ? 'Exportando...' : 'Excel'}
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
                Guardado
              </>
            ) : (
              <>
                <Bookmark className="h-3.5 w-3.5" />
                {isSaving ? 'Guardando...' : 'Guardar'}
              </>
            )}
            </button>
          </div>
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
                <span className="text-sm text-light-secondary">Marca detectada:</span>
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

      {/* Verified Badge Banner */}
      <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-metric-excellent/10 border border-metric-excellent/20">
        <ShieldCheck className="w-5 h-5 text-metric-excellent flex-shrink-0" />
        <p className="text-sm text-light-secondary">
          <span className="font-medium text-metric-excellent">Perfiles verificados:</span>{' '}
          Cada influencer ha sido analizado y validado para garantizar métricas reales y audiencias auténticas.
        </p>
      </div>

      {/* Results Grid/List */}
      {searchResponse.results.length > 0 ? (
        viewMode === 'cards' ? (
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-2">
            {searchResponse.results.map((result, index) => (
              <InfluencerCard
                key={result.influencer_id}
                influencer={result}
                index={index}
                isSelected={selectedIndex === index}
                onCopy={handleCopy}
              />
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {searchResponse.results.map((result, index) => (
              <InfluencerRow
                key={result.influencer_id}
                influencer={result}
                index={index}
                isSelected={selectedIndex === index}
                onCopy={handleCopy}
              />
            ))}
          </div>
        )
      ) : (
        <div className="text-center py-16">
          <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-dark-secondary border border-dark-border flex items-center justify-center">
            <Sparkles className="w-8 h-8 text-light-tertiary" />
          </div>
          <h3 className="font-serif text-xl text-light-primary mb-2">
            Sin resultados
          </h3>
          <p className="text-light-secondary text-sm max-w-md mx-auto">
            Ningún influencer coincide con tus criterios. Prueba a ajustar los filtros o ampliar tu búsqueda.
          </p>
        </div>
      )}
    </div>
  );
});
