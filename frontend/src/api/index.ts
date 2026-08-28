import axios from 'axios';
import type { Book, BookSort, Highlight, HighlightWithBook, ImportLog, ImportSummary, InsightsSummary, RelatedHighlight, SparkHighlight, SparkStreak, Summary, AIGenreRecommendation, Thought, AIGeneration } from '../types';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? ''
});

export async function getHealth() {
  const response = await api.get<{ status: string; app: string }>('/health');
  return response.data;
}

export async function shutdownSynapse() {
  const response = await api.post<{ status: string }>('/api/shutdown');
  return response.data;
}

export async function getSummary() {
  const response = await api.get<Summary>('/api/summary');
  return response.data;
}

export async function getInsights() {
  const response = await api.get<InsightsSummary>('/api/insights');
  return response.data;
}

export async function getAIRecommendations(refresh = false) {
  const response = await api.get<AIGenreRecommendation[]>(`/api/insights/ai-recommendations?refresh=${refresh}`);
  return response.data;
}

export async function getAIRecommendationsHistory() {
  const response = await api.get<AIGeneration[]>('/api/insights/ai-recommendations/history');
  return response.data;
}

export async function getBooks(sort: BookSort = 'title') {
  const response = await api.get<Book[]>('/api/books', { params: { sort } });
  return response.data;
}

export async function getBook(bookId: string) {
  const response = await api.get<{ book: Book; highlights: Highlight[] }>(`/api/books/${bookId}`);
  return response.data;
}

export async function getImports() {
  const response = await api.get<ImportLog[]>('/api/imports');
  return response.data;
}

export async function importDefaultClippings() {
  const response = await api.post<ImportSummary>('/api/import/default');
  return response.data;
}

export async function uploadClippings(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post<ImportSummary>('/api/import/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return response.data;
}

export async function importKindleNotebook(headed: boolean = false, resetSession: boolean = false) {
  const response = await api.post<ImportSummary>('/api/import/kindle-notebook', { 
    headed, 
    reset_session: resetSession 
  });
  return response.data;
}


export async function getSpark() {
  const response = await api.get<{ highlight: SparkHighlight | null }>('/api/spark');
  return response.data;
}

export async function markSparkSeen(highlightId: string) {
  const response = await api.post<{ id: string; last_seen_at?: string | null }>(`/api/highlights/${highlightId}/seen`);
  return response.data;
}

export async function favoriteHighlight(highlightId: string) {
  const response = await api.post<{ id: string; is_favorite: boolean }>(`/api/highlights/${highlightId}/favorite`);
  return response.data;
}

export async function unfavoriteHighlight(highlightId: string) {
  const response = await api.delete<{ id: string; is_favorite: boolean }>(`/api/highlights/${highlightId}/favorite`);
  return response.data;
}

export async function hideHighlight(highlightId: string) {
  const response = await api.post<{ id: string; is_hidden: boolean }>(`/api/highlights/${highlightId}/hidden`);
  return response.data;
}

export async function unhideHighlight(highlightId: string) {
  const response = await api.delete<{ id: string; is_hidden: boolean }>(`/api/highlights/${highlightId}/hidden`);
  return response.data;
}

export async function getFavoriteHighlights() {
  const response = await api.get<HighlightWithBook[]>('/api/highlights/favorites');
  return response.data;
}

export async function getHiddenHighlights() {
  const response = await api.get<HighlightWithBook[]>('/api/highlights/hidden');
  return response.data;
}

export async function searchHighlights(query: string) {
  const response = await api.get<HighlightWithBook[]>('/api/highlights/search', { params: { q: query } });
  return response.data;
}

export async function getOnThisDay() {
  const response = await api.get<HighlightWithBook[]>('/api/spark/on-this-day');
  return response.data;
}

export async function getSparkStreak() {
  const response = await api.get<SparkStreak>('/api/spark/streak');
  return response.data;
}

export async function getCoverStatus() {
  const response = await api.get<{ missing: number }>('/api/books/covers/status');
  return response.data;
}

export async function backfillCovers() {
  const response = await api.post<{ processed: number; found: number }>('/api/books/covers/backfill');
  return response.data;
}

export async function getEmbeddingStatus() {
  const response = await api.get<{ missing: number }>('/api/embeddings/status');
  return response.data;
}

export async function backfillEmbeddings() {
  const response = await api.post<{ processed: number; error?: string }>('/api/embeddings/backfill');
  return response.data;
}

export async function getRelatedHighlights(highlightId: string) {
  const response = await api.get<RelatedHighlight[]>(`/api/highlights/${highlightId}/related`);
  return response.data;
}

export async function addThought(highlightId: string, content: string) {
  const response = await api.post<Thought>(`/api/highlights/${highlightId}/thoughts`, { content });
  return response.data;
}
