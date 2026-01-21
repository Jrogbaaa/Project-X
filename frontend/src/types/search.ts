export interface FilterConfig {
  min_credibility_score: number;
  min_engagement_rate?: number;
  min_spain_audience_pct: number;
  min_follower_growth_rate?: number;
}

export interface RankingWeights {
  credibility: number;
  engagement: number;
  audience_match: number;
  growth: number;
  geography: number;
}

export interface SearchRequest {
  query: string;
  filters?: FilterConfig;
  ranking_weights?: RankingWeights;
  limit?: number;
}

export interface ParsedSearchQuery {
  target_count: number;
  influencer_gender: 'male' | 'female' | 'any';
  target_audience_gender?: 'male' | 'female' | 'any' | null;
  brand_name?: string | null;
  brand_category?: string | null;
  content_themes: string[];
  target_age_ranges: string[];
  min_spain_audience_pct: number;
  min_credibility_score: number;
  min_engagement_rate?: number | null;
  suggested_ranking_weights?: RankingWeights | null;
  search_keywords: string[];
  parsing_confidence: number;
  reasoning: string;
}

export interface ScoreComponents {
  credibility: number;
  engagement: number;
  audience_match: number;
  growth: number;
  geography: number;
}

export interface InfluencerData {
  id: string;
  username: string;
  display_name?: string | null;
  profile_picture_url?: string | null;
  bio?: string | null;
  profile_url?: string | null;
  is_verified: boolean;
  follower_count: number;
  following_count?: number;
  post_count?: number;
  credibility_score?: number | null;
  engagement_rate?: number | null;
  follower_growth_rate_6m?: number | null;
  avg_likes: number;
  avg_comments: number;
  avg_views?: number | null;
  audience_genders: Record<string, number>;
  audience_age_distribution: Record<string, number>;
  audience_geography: Record<string, number>;
  platform_type?: string;
  cached_at?: string | null;
}

export interface RankedInfluencer {
  influencer_id: string;
  username: string;
  rank_position: number;
  relevance_score: number;
  scores: ScoreComponents;
  raw_data: InfluencerData;
}

export interface SearchResponse {
  search_id: string;
  query: string;
  parsed_query: ParsedSearchQuery;
  filters_applied: FilterConfig;
  results: RankedInfluencer[];
  total_candidates: number;
  total_after_filter: number;
  executed_at: string;
}

export interface SavedSearch {
  id: string;
  name: string;
  description?: string | null;
  raw_query: string;
  parsed_query: Record<string, unknown>;
  result_count: number;
  created_at: string;
  updated_at: string;
}

export interface SearchHistoryItem {
  id: string;
  raw_query: string;
  result_count: number;
  is_saved: boolean;
  saved_name?: string | null;
  executed_at: string;
}
