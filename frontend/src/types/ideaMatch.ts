export interface IdeaScore {
  brand_fit: number;
  originality: number;
  strategic_relevance: number;
  feasibility: number;
  engagement_potential: number;
  total: number;
}

export interface IdeaCard {
  title: string;
  concept: string;
  format: string;
  platforms: string[];
  tone: string[];
  framework_used: string;
  framework_rationale: string;
  avoid: string;
  engagement_type: string;
  score: IdeaScore;
}

export interface BrandAttributes {
  brand_name: string;
  category: string;
  audience: string;
  positioning: string;
  tone: string[];
  visual_style: string;
  price_tier: string;
  platform_focus: string[];
  product_benefit: string;
  growth_goal: string;
  archetype: string;
  description: string;
  competitors: string[];
  confidence: number;
}

export interface IdeaBrief {
  id: string;
  brand_vertical: string;
  brand_summary: string;
  archetype: string;
  archetype_rationale: string;
  ideas: IdeaCard[];
  bold_bet: IdeaCard;
  brand_attributes: BrandAttributes;
  frameworks_selected: string[];
  retrieved_examples_count: number;
}

export const FRAMEWORK_LABELS: Record<string, string> = {
  goldenberg_extreme_consequence: 'Extreme Consequence',
  goldenberg_pictorial_analogy: 'Pictorial Analogy',
  goldenberg_competition: 'Competition',
  goldenberg_interactive_experiment: 'Interactive Experiment',
  goldenberg_dimensional_alteration: 'Dimensional Alteration',
  goldenberg_replacement: 'Replacement',
  repetition_break: 'Repetition-Break',
  visual_metaphor: 'Visual Metaphor',
  schema_congruity: 'Schema Congruity',
  archetype: 'Archetype',
};

export const FRAMEWORK_DESCRIPTIONS: Record<string, string> = {
  goldenberg_extreme_consequence: 'Shows the visceral consequence of the product\'s absence or presence',
  goldenberg_pictorial_analogy: 'Replaces the product with a visual metaphor for the benefit',
  goldenberg_competition: 'Contrasts the brand against an inferior alternative',
  goldenberg_interactive_experiment: 'The audience participation is the ad itself',
  goldenberg_dimensional_alteration: 'Magnifies or distorts a product dimension to dramatise significance',
  goldenberg_replacement: 'The product replaces a familiar object in a logical but unexpected way',
  repetition_break: 'Establishes a pattern, repeats it, then breaks it with a surprising twist',
  visual_metaphor: 'Synthesises the product with a conceptually similar object',
  schema_congruity: 'Slightly violates audience expectations for maximum persuasion',
  archetype: 'Positions the brand through a classic character archetype',
};

export const ENGAGEMENT_TYPE_LABELS: Record<string, string> = {
  awareness: 'Brand Awareness',
  engagement: 'Audience Engagement',
  persuasion: 'Product Persuasion',
  brand_personality: 'Brand Personality',
};
