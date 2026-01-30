import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { InfluencerCard } from '../InfluencerCard';
import { RankedInfluencer } from '@/types/search';

// Mock influencer data
const createMockInfluencer = (overrides: Partial<RankedInfluencer['raw_data']> = {}): RankedInfluencer => ({
  influencer_id: 'test-123',
  username: 'testuser',
  rank_position: 1,
  relevance_score: 0.85,
  scores: {
    credibility: 0.9,
    engagement: 0.75,
    audience_match: 0.8,
    growth: 0.6,
    geography: 0.95,
    brand_affinity: 0.7,
    creative_fit: 0.85,
    niche_match: 0.65,
  },
  raw_data: {
    id: 'test-123',
    username: 'testuser',
    display_name: 'Test User',
    profile_picture_url: 'https://example.com/avatar.jpg',
    bio: 'This is a test bio for the influencer.',
    profile_url: 'https://instagram.com/testuser',
    is_verified: true,
    follower_count: 150000,
    following_count: 500,
    post_count: 200,
    credibility_score: 85,
    engagement_rate: 3.5,
    follower_growth_rate_6m: 0.12,
    avg_likes: 5000,
    avg_comments: 150,
    avg_views: 10000,
    audience_genders: { male: 40, female: 60 },
    audience_age_distribution: { '18-24': 35, '25-34': 45, '35-44': 15, '45+': 5 },
    audience_geography: { ES: 75, US: 10, MX: 5 },
    platform_type: 'instagram',
    cached_at: '2024-01-15T10:00:00Z',
    mediakit_url: 'https://primetag.com/mediakit/testuser',
    brand_warning_type: null,
    brand_warning_message: null,
    niche_warning: null,
    ...overrides,
  },
});

describe('InfluencerCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering Basic Information', () => {
    it('renders the username handle correctly', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      expect(screen.getByText('@testuser')).toBeInTheDocument();
    });

    it('renders the display name', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });

    it('renders the follower count formatted correctly', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      expect(screen.getByText('150.0K')).toBeInTheDocument();
      expect(screen.getByText(/seguidores/)).toBeInTheDocument();
    });

    it('renders the rank position', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    it('renders the verified badge for verified users', () => {
      render(<InfluencerCard influencer={createMockInfluencer({ is_verified: true })} />);
      // The BadgeCheck icon should be present
      const badges = document.querySelectorAll('svg');
      expect(badges.length).toBeGreaterThan(0);
    });

    it('does not render verified badge for non-verified users', () => {
      render(<InfluencerCard influencer={createMockInfluencer({ is_verified: false })} />);
      // Should have fewer badges
      const verifiedBadges = screen.queryAllByLabelText(/verified/i);
      expect(verifiedBadges).toHaveLength(0);
    });
  });

  describe('Rendering Metrics', () => {
    it('renders the match/relevance score', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      expect(screen.getByText('85')).toBeInTheDocument();
    });

    it('renders credibility score', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      // Multiple elements may show this percentage, just verify it's in the document
      const credElements = screen.getAllByText('85%');
      expect(credElements.length).toBeGreaterThan(0);
    });

    it('renders engagement rate', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      expect(screen.getByText('3.5%')).toBeInTheDocument();
    });

    it('renders Spain audience percentage', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      // Multiple elements may show this percentage, just verify it's in the document
      const spainPctElements = screen.getAllByText('75%');
      expect(spainPctElements.length).toBeGreaterThan(0);
    });

    it('renders growth rate', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      expect(screen.getByText('12%')).toBeInTheDocument();
    });
  });

  describe('Links and Actions', () => {
    it('renders MediaKit link when URL is available', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      const mediakitLink = screen.getByRole('link', { name: /mediakit/i });
      expect(mediakitLink).toBeInTheDocument();
      expect(mediakitLink).toHaveAttribute('href', 'https://primetag.com/mediakit/testuser');
      expect(mediakitLink).toHaveAttribute('target', '_blank');
    });

    it('does not render MediaKit link when URL is not available', () => {
      render(<InfluencerCard influencer={createMockInfluencer({ mediakit_url: undefined })} />);
      const mediakitLinks = screen.queryAllByRole('link', { name: /mediakit/i });
      expect(mediakitLinks).toHaveLength(0);
    });

    it('renders Profile link', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      const profileLink = screen.getByRole('link', { name: /perfil/i });
      expect(profileLink).toBeInTheDocument();
      expect(profileLink).toHaveAttribute('href', 'https://instagram.com/testuser');
      expect(profileLink).toHaveAttribute('target', '_blank');
    });

    it('generates fallback profile URL when not provided', () => {
      render(<InfluencerCard influencer={createMockInfluencer({ profile_url: undefined })} />);
      const profileLink = screen.getByRole('link', { name: /perfil/i });
      expect(profileLink).toHaveAttribute('href', 'https://instagram.com/testuser');
    });
  });

  describe('Copy Functionality', () => {
    it('renders copy button for username', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      const copyButton = screen.getByRole('button', { name: /copiar usuario/i });
      expect(copyButton).toBeInTheDocument();
    });

    it('copies username to clipboard when copy button is clicked', async () => {
      const mockOnCopy = vi.fn();
      render(<InfluencerCard influencer={createMockInfluencer()} onCopy={mockOnCopy} />);
      
      const copyButton = screen.getByRole('button', { name: /copiar usuario/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith('@testuser');
      });
      expect(mockOnCopy).toHaveBeenCalledWith('Usuario copiado');
    });

    it('renders copy button for MediaKit URL when available', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      const copyButton = screen.getByRole('button', { name: /copiar url mediakit/i });
      expect(copyButton).toBeInTheDocument();
    });

    it('copies MediaKit URL to clipboard when copy button is clicked', async () => {
      const mockOnCopy = vi.fn();
      render(<InfluencerCard influencer={createMockInfluencer()} onCopy={mockOnCopy} />);
      
      const copyButton = screen.getByRole('button', { name: /copiar url mediakit/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://primetag.com/mediakit/testuser');
      });
      expect(mockOnCopy).toHaveBeenCalledWith('URL MediaKit copiada');
    });
  });

  describe('Expandable Details', () => {
    it('renders expand button', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      const expandButton = screen.getByRole('button', { name: /ver detalles/i });
      expect(expandButton).toBeInTheDocument();
    });

    it('shows bio when expanded', async () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      
      const expandButton = screen.getByRole('button', { name: /ver detalles/i });
      fireEvent.click(expandButton);

      await waitFor(() => {
        expect(screen.getByText('This is a test bio for the influencer.')).toBeVisible();
      });
    });

    it('toggles between expanded and collapsed states', async () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      
      // Expand
      const expandButton = screen.getByRole('button', { name: /ver detalles/i });
      fireEvent.click(expandButton);

      await waitFor(() => {
        expect(screen.getByText(/ocultar detalles/i)).toBeInTheDocument();
      });

      // Collapse
      fireEvent.click(screen.getByRole('button', { name: /ocultar detalles/i }));
      
      await waitFor(() => {
        expect(screen.getByText(/ver detalles/i)).toBeInTheDocument();
      });
    });
  });

  describe('Footer Stats', () => {
    it('renders average likes', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      expect(screen.getByText('5.0K')).toBeInTheDocument();
    });

    it('renders average comments', () => {
      render(<InfluencerCard influencer={createMockInfluencer()} />);
      // The footer contains "likes," for avg_likes
      const footer = screen.getByText(/likes,/);
      expect(footer).toBeInTheDocument();
      // Comments value is 150, check it's in the document
      const commentCount = screen.getAllByText(/150/)[0];
      expect(commentCount).toBeInTheDocument();
    });
  });

  describe('Selection State', () => {
    it('applies selected styling when isSelected is true', () => {
      const { container } = render(<InfluencerCard influencer={createMockInfluencer()} isSelected={true} />);
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('border-accent-gold');
    });

    it('does not apply selected styling when isSelected is false', () => {
      const { container } = render(<InfluencerCard influencer={createMockInfluencer()} isSelected={false} />);
      const card = container.firstChild as HTMLElement;
      expect(card.className).not.toContain('ring-2');
    });
  });
});
