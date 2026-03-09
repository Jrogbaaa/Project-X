import { IdeaBrief } from '@/types/ideaMatch';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function generateIdeaBrief(brand: string): Promise<IdeaBrief> {
  const response = await fetch(`${API_BASE}/api/idea-match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ brand }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }

  return response.json();
}
