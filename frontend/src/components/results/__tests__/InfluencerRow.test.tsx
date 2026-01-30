import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { InfluencerRow } from '../InfluencerRow';
import { RankedInfluencer } from '@/types/search';

// Mock influencer data
const createMockInfluencer = (overrides: Partial<RankedInfluencer['raw_data']> = {}): RankedInfluencer => ({
  influencer_id: 'test-456',
  username: 'rowuser',
  rank_position: 3,
  relevance_score: 0.78,
  scores: {
    credibility: 0.85,
    engagement: 0.70,
    audience_match: 0.75,
    growth: 0.55,
    geography: 0.90,
    brand_affinity: 0.65,
    creative_fit: 0.80,
    niche_match: 0.60,
  },
  raw_data: {
    id: 'test-456',
    username: 'rowuser',
    display_name: 'Row User',
    profile_picture_url: 'https://example.com/row-avatar.jpg',
    bio: 'Bio for row user.',
    profile_url: 'https://instagram.com/rowuser',
    is_verified: false,
    follower_count: 250000,
    following_count: 800,
    post_count: 350,
    credibility_score: 82,
    engagement_rate: 2.8,
    follower_growth_rate_6m: 0.08,
    avg_likes: 7000,
    avg_comments: 200,
    avg_views: 15000,
    audience_genders: { male: 55, female: 45 },
    audience_age_distribution: { '18-24': 40, '25-34': 40, '35-44': 15, '45+': 5 },
    audience_geography: { ES: 68, UK: 15, FR: 8 },
    platform_type: 'instagram',
    cached_at: '2024-01-15T12:00:00Z',
    mediakit_url: 'https://primetag.com/mediakit/rowuser',
    brand_warning_type: null,
    brand_warning_message: null,
    niche_warning: null,
    ...overrides,
  },
});

describe('InfluencerRow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering Basic Information', () => {
    it('renders the username handle correctly', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      expect(screen.getByText('@rowuser')).toBeInTheDocument();
    });

    it('renders the follower count formatted correctly', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      expect(screen.getByText('250.0K')).toBeInTheDocument();
      expect(screen.getByText(/seguidores/)).toBeInTheDocument();
    });

    it('renders the rank position', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('renders the verified badge for verified users', () => {
      render(<InfluencerRow influencer={createMockInfluencer({ is_verified: true })} />);
      // Verified badge should be present - check for SVG elements
      const badges = document.querySelectorAll('svg');
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  describe('Rendering Metrics (visible without expansion)', () => {
    it('renders the match/relevance score', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      expect(screen.getByText('78%')).toBeInTheDocument();
    });

    it('renders credibility score', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      expect(screen.getByText('82%')).toBeInTheDocument();
    });

    it('renders engagement rate', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      expect(screen.getByText('2.8%')).toBeInTheDocument();
    });

    it('renders Spain audience percentage with ES label', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      expect(screen.getByText('68% ES')).toBeInTheDocument();
    });

    it('renders growth rate', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      expect(screen.getByText('8%')).toBeInTheDocument();
    });
  });

  describe('Links and Actions', () => {
    it('renders MediaKit link when URL is available', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      const mediakitLink = screen.getByRole('link', { name: /mediakit/i });
      expect(mediakitLink).toBeInTheDocument();
      expect(mediakitLink).toHaveAttribute('href', 'https://primetag.com/mediakit/rowuser');
      expect(mediakitLink).toHaveAttribute('target', '_blank');
    });

    it('does not render MediaKit link when URL is not available', () => {
      render(<InfluencerRow influencer={createMockInfluencer({ mediakit_url: undefined })} />);
      const mediakitLinks = screen.queryAllByRole('link', { name: /mediakit/i });
      expect(mediakitLinks).toHaveLength(0);
    });

    it('renders Profile link', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      const profileLink = screen.getByRole('link', { name: /perfil/i });
      expect(profileLink).toBeInTheDocument();
      expect(profileLink).toHaveAttribute('href', 'https://instagram.com/rowuser');
      expect(profileLink).toHaveAttribute('target', '_blank');
    });

    it('generates fallback profile URL when not provided', () => {
      render(<InfluencerRow influencer={createMockInfluencer({ profile_url: undefined })} />);
      const profileLink = screen.getByRole('link', { name: /perfil/i });
      expect(profileLink).toHaveAttribute('href', 'https://instagram.com/rowuser');
    });
  });

  describe('Copy Functionality', () => {
    it('renders copy button for username', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      const copyButton = screen.getByRole('button', { name: /copiar usuario/i });
      expect(copyButton).toBeInTheDocument();
    });

    it('copies username to clipboard when copy button is clicked', async () => {
      const mockOnCopy = vi.fn();
      render(<InfluencerRow influencer={createMockInfluencer()} onCopy={mockOnCopy} />);
      
      const copyButton = screen.getByRole('button', { name: /copiar usuario/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith('@rowuser');
      });
      expect(mockOnCopy).toHaveBeenCalledWith('Usuario copiado');
    });

    it('renders copy button for MediaKit URL when available', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      const copyButton = screen.getByRole('button', { name: /copiar url mediakit/i });
      expect(copyButton).toBeInTheDocument();
    });

    it('copies MediaKit URL to clipboard when copy button is clicked', async () => {
      const mockOnCopy = vi.fn();
      render(<InfluencerRow influencer={createMockInfluencer()} onCopy={mockOnCopy} />);
      
      const copyButton = screen.getByRole('button', { name: /copiar url mediakit/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://primetag.com/mediakit/rowuser');
      });
      expect(mockOnCopy).toHaveBeenCalledWith('URL MediaKit copiada');
    });
  });

  describe('Selection State', () => {
    it('applies selected styling when isSelected is true', () => {
      const { container } = render(<InfluencerRow influencer={createMockInfluencer()} isSelected={true} />);
      const row = container.firstChild as HTMLElement;
      expect(row.className).toContain('border-accent-gold');
      expect(row.className).toContain('ring-1');
    });

    it('does not apply selected styling when isSelected is false', () => {
      const { container } = render(<InfluencerRow influencer={createMockInfluencer()} isSelected={false} />);
      const row = container.firstChild as HTMLElement;
      expect(row.className).not.toContain('ring-1');
    });
  });

  describe('Data Index Attribute', () => {
    it('sets the correct data-index attribute for keyboard navigation', () => {
      const { container } = render(<InfluencerRow influencer={createMockInfluencer()} index={5} />);
      const row = container.firstChild as HTMLElement;
      expect(row.getAttribute('data-index')).toBe('5');
    });
  });

  describe('Compact Display', () => {
    it('displays all essential information without requiring expansion', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      
      // All these should be visible immediately without any click
      expect(screen.getByText('@rowuser')).toBeVisible();
      expect(screen.getByText('250.0K')).toBeVisible();
      expect(screen.getByText('78%')).toBeVisible(); // Match score
      expect(screen.getByText('82%')).toBeVisible(); // Credibility
      expect(screen.getByText('2.8%')).toBeVisible(); // Engagement
      expect(screen.getByRole('link', { name: /perfil/i })).toBeVisible();
    });

    it('displays MediaKit link without requiring expansion', () => {
      render(<InfluencerRow influencer={createMockInfluencer()} />);
      expect(screen.getByRole('link', { name: /mediakit/i })).toBeVisible();
    });
  });

  describe('Handles Missing Data Gracefully', () => {
    it('shows N/A for missing credibility score', () => {
      render(<InfluencerRow influencer={createMockInfluencer({ credibility_score: undefined })} />);
      expect(screen.getByText('N/A')).toBeInTheDocument();
    });

    it('shows N/A for missing engagement rate', () => {
      render(<InfluencerRow influencer={createMockInfluencer({ engagement_rate: undefined })} />);
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('shows N/A for missing growth rate', () => {
      render(<InfluencerRow influencer={createMockInfluencer({ follower_growth_rate_6m: undefined })} />);
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('shows 0% ES for missing Spain audience', () => {
      render(<InfluencerRow influencer={createMockInfluencer({ audience_geography: {} })} />);
      expect(screen.getByText('0% ES')).toBeInTheDocument();
    });
  });
});
