'use client';

import { useState, forwardRef } from 'react';
import {
  Download, FileSpreadsheet, Bookmark, CheckCircle,
  Tag, Sparkles, LayoutGrid, List, ShieldCheck,
} from 'lucide-react';
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
    } catch {
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
    } catch {
      onToast?.('Error al guardar');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCopy = (message: string) => {
    onToast?.(message);
  };

  return (
    <div className="space-y-5" ref={ref}>

      {/* ── Sticky results header ──────────────────────────────── */}
      <div className="sticky top-0 z-20 -mx-6 px-6 py-3.5 bg-dark-primary/95 backdrop-blur-sm border-b border-dark-border/40">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">

          {/* Counts */}
          <div>
            <div className="flex items-center gap-2.5 mb-0.5">
              <h2 className="font-serif text-[1.25rem] text-light-primary font-[500]">Resultados</h2>
              <div className="h-px w-10 bg-ember-warm/35" />
            </div>
            <p className="text-xs text-light-tertiary/70">
              <span className="font-mono text-light-secondary">{searchResponse.total_candidates}</span> candidatos
              {' · '}
              <span className="font-mono text-light-secondary">{searchResponse.total_after_filter}</span> pasaron filtros
              {' · '}
              top <span className="font-mono text-ember-warm">{searchResponse.results.length}</span>
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">

            {/* View toggle */}
            <div className="flex items-center border border-dark-border/60 rounded-lg p-0.5 mr-1 bg-dark-secondary/60">
              <button
                onClick={() => setViewMode('cards')}
                className={cn(
                  'p-1.5 rounded-md transition-all',
                  viewMode === 'cards'
                    ? 'bg-dark-ash text-light-primary shadow-sm'
                    : 'text-light-tertiary hover:text-light-secondary'
                )}
                aria-label="Vista en tarjetas"
                title="Tarjetas"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={cn(
                  'p-1.5 rounded-md transition-all',
                  viewMode === 'list'
                    ? 'bg-dark-ash text-light-primary shadow-sm'
                    : 'text-light-tertiary hover:text-light-secondary'
                )}
                aria-label="Vista en lista"
                title="Lista"
              >
                <List className="w-3.5 h-3.5" />
              </button>
            </div>

            <button
              onClick={() => handleExport('csv')}
              disabled={isExporting !== null}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
                         text-light-secondary bg-dark-secondary border border-dark-border/60 rounded-lg
                         hover:text-light-primary hover:border-dark-border
                         disabled:opacity-50 transition-all"
            >
              <Download className="h-3 w-3" />
              {isExporting === 'csv' ? 'Exportando...' : 'CSV'}
            </button>

            <button
              onClick={() => handleExport('excel')}
              disabled={isExporting !== null}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
                         text-light-secondary bg-dark-secondary border border-dark-border/60 rounded-lg
                         hover:text-light-primary hover:border-dark-border
                         disabled:opacity-50 transition-all"
            >
              <FileSpreadsheet className="h-3 w-3" />
              {isExporting === 'excel' ? 'Exportando...' : 'Excel'}
            </button>

            <button
              onClick={handleSave}
              disabled={isSaving || isSaved}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all border ${
                isSaved
                  ? 'text-metric-excellent bg-metric-excellent/[0.08] border-metric-excellent/25'
                  : 'text-ember-warm bg-ember-warm/[0.08] border-ember-warm/25 hover:bg-ember-warm/[0.12]'
              } disabled:opacity-50`}
            >
              {isSaved ? (
                <>
                  <CheckCircle className="h-3 w-3" />
                  Guardado
                </>
              ) : (
                <>
                  <Bookmark className="h-3 w-3" />
                  {isSaving ? 'Guardando...' : 'Guardar'}
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* ── Brand detection card ───────────────────────────────── */}
      {searchResponse.parsed_query.brand_name && (
        <div className="bg-dark-secondary rounded-xl border border-dark-border/60 p-4 shadow-card">
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-lg bg-ice-bright/[0.10] flex items-center justify-center flex-shrink-0 border border-ice-bright/20">
              <Sparkles className="w-3.5 h-3.5 text-ice-bright" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className="text-xs text-light-secondary">Marca detectada:</span>
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-ember-warm/[0.10] text-ember-warm border border-ember-warm/[0.22]">
                  {searchResponse.parsed_query.brand_name}
                </span>
                {searchResponse.parsed_query.brand_category && (
                  <span className="px-2 py-0.5 rounded text-xs bg-dark-ash text-light-secondary border border-dark-border/50">
                    {searchResponse.parsed_query.brand_category.replace(/_/g, ' ')}
                  </span>
                )}
              </div>
              {searchResponse.parsed_query.content_themes.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap mt-1">
                  <Tag className="w-2.5 h-2.5 text-light-tertiary/60" />
                  {searchResponse.parsed_query.content_themes.slice(0, 5).map((theme, i) => (
                    <span key={i} className="text-[11px] text-light-tertiary/70">
                      {theme.replace(/_/g, ' ')}{i < Math.min(4, searchResponse.parsed_query.content_themes.length - 1) ? ' ·' : ''}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Verified banner ────────────────────────────────────── */}
      <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-lg bg-metric-excellent/[0.07] border border-metric-excellent/20">
        <ShieldCheck className="w-3.5 h-3.5 text-metric-excellent flex-shrink-0" />
        <p className="text-xs text-light-secondary">
          <span className="font-medium text-metric-excellent">Perfiles verificados:</span>{' '}
          Cada influencer ha sido analizado para garantizar métricas reales y audiencias auténticas.
        </p>
      </div>

      {/* ── Results ───────────────────────────────────────────── */}
      {searchResponse.results.length > 0 ? (
        viewMode === 'cards' ? (
          <div className="grid gap-4 md:grid-cols-2">
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
          <div className="flex flex-col divide-y divide-dark-border/40 border border-dark-border/60 rounded-xl overflow-hidden bg-dark-secondary shadow-card">
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
          <div className="w-12 h-12 mx-auto mb-5 rounded-full bg-dark-secondary border border-dark-border/60 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-light-tertiary/40" />
          </div>
          <h3 className="font-serif text-xl text-light-primary mb-2">Sin resultados</h3>
          <p className="text-light-secondary text-sm max-w-md mx-auto">
            Ningún influencer coincide con tus criterios. Prueba a ajustar los filtros o ampliar tu búsqueda.
          </p>
        </div>
      )}
    </div>
  );
});
