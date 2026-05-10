export type Book = {
  id: string;
  title: string;
  author?: string | null;
  cover_url?: string | null;
  total_highlights: number;
  last_imported_at?: string;
};

export type Highlight = {
  id: string;
  book_id: string;
  content: string;
  note?: string | null;
  highlight_type: string;
  page?: number | null;
  location_start?: number | null;
  location_end?: number | null;
  date_added?: string | null;
  source: string;
  thoughts?: Thought[];
};

export type Thought = {
  id: string;
  content: string;
  created_at: string;
};

export type RelatedHighlight = {
  id: string;
  book_id: string;
  content: string;
  note?: string | null;
  page?: number | null;
  location_start?: number | null;
  location_end?: number | null;
  quoted_at?: string | null;
  source: string;
  book_title: string;
};

export type Summary = {
  books: number;
  highlights: number;
  imports: number;
  latest_import_at?: string | null;
};

export type ImportSummary = {
  source: string;
  file_name?: string | null;
  records_seen: number;
  records_created: number;
  records_skipped: number;
  records_failed: number;
  books_created: number;
  import_log_id: string;
};

export type ImportLog = {
  id: string;
  source: string;
  file_name?: string | null;
  records_seen: number;
  records_created: number;
  records_skipped: number;
  records_failed: number;
  created_at: string;
  error_summary?: string | null;
};


export type SparkHighlight = {
  id: string;
  content: string;
  note?: string | null;
  page?: number | null;
  location_start?: number | null;
  location_end?: number | null;
  quoted_at?: string | null;
  book_title: string;
  author?: string | null;
  is_favorite: boolean;
  is_hidden: boolean;
  last_seen_at?: string | null;
  thoughts?: Thought[];
};

export type InsightsSummary = {
  summary: Summary;
  timeline: { month: string; count: number }[];
  top_authors: { name: string; total_highlights: number; total_books: number }[];
  books_to_revisit: { id: string; title: string; author?: string | null; total_highlights: number }[];
  signals: {
    favorites: number;
    hidden: number;
    seen: number;
  };
};

export type AIRecommendation = {
  title: string;
  author: string;
  reason: string;
};

export type AIGenreRecommendation = {
  genre: string;
  books: AIRecommendation[];
};

export type AIGeneration = {
  id: string;
  created_at: string;
  recommendations: AIGenreRecommendation[];
};
