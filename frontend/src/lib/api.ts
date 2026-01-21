import axios from 'axios';
import { SearchRequest, SearchResponse, SavedSearch, SearchHistoryItem } from '@/types/search';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export async function searchInfluencers(request: SearchRequest): Promise<SearchResponse> {
  const response = await api.post<SearchResponse>('/search/', request);
  return response.data;
}

export async function getSearch(searchId: string): Promise<SearchResponse> {
  const response = await api.get<SearchResponse>(`/search/${searchId}`);
  return response.data;
}

export async function saveSearch(
  searchId: string,
  name: string,
  description?: string
): Promise<SavedSearch> {
  const response = await api.post<SavedSearch>(`/search/${searchId}/save`, {
    name,
    description,
  });
  return response.data;
}

export async function getSavedSearches(limit = 50): Promise<SavedSearch[]> {
  const response = await api.get<SavedSearch[]>('/search/saved/list', {
    params: { limit },
  });
  return response.data;
}

export async function getSearchHistory(limit = 50): Promise<SearchHistoryItem[]> {
  const response = await api.get<SearchHistoryItem[]>('/search/history/list', {
    params: { limit },
  });
  return response.data;
}

export function getExportCsvUrl(searchId: string): string {
  return `/api/exports/${searchId}/csv`;
}

export function getExportExcelUrl(searchId: string): string {
  return `/api/exports/${searchId}/excel`;
}

export async function downloadExport(searchId: string, format: 'csv' | 'excel'): Promise<void> {
  const url = format === 'csv' ? getExportCsvUrl(searchId) : getExportExcelUrl(searchId);

  const response = await api.get(url, {
    responseType: 'blob',
  });

  const contentDisposition = response.headers['content-disposition'];
  let filename = `influencers_${searchId}.${format === 'csv' ? 'csv' : 'xlsx'}`;

  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename=(.+)/);
    if (filenameMatch) {
      filename = filenameMatch[1];
    }
  }

  // Create download link
  const blob = new Blob([response.data]);
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = downloadUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(downloadUrl);
}
