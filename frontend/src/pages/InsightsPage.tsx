import { useEffect, useState } from 'react';
import { Sparkles, RefreshCw, History } from 'lucide-react';
import { getInsights, getAIRecommendations, getAIRecommendationsHistory } from '../api';
import type { InsightsSummary, AIGenreRecommendation, AIGeneration } from '../types';

export default function InsightsPage() {
  const [data, setData] = useState<InsightsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [aiRecs, setAiRecs] = useState<AIGenreRecommendation[] | null>(null);
  const [aiHistory, setAiHistory] = useState<AIGeneration[]>([]);
  const [loadingAi, setLoadingAi] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  async function loadAIRecommendations(refresh = false) {
    setLoadingAi(true);
    setAiError(null);
    try {
      const recs = await getAIRecommendations(refresh);
      setAiRecs(recs);
      const history = await getAIRecommendationsHistory();
      setAiHistory(history);
    } catch (err: any) {
      setAiError(err.response?.data?.detail || err.message || 'Failed to fetch AI recommendations');
    } finally {
      setLoadingAi(false);
    }
  }

  useEffect(() => {
    getInsights().then(setData).catch((e) => setError(e.message));
    // Load cached recommendations and history on mount
    getAIRecommendations(false)
      .then(setAiRecs)
      .catch(() => {}); // silently ignore if no API key
    getAIRecommendationsHistory()
      .then(setAiHistory)
      .catch(() => {});
  }, []);

  if (error) {
    return <p className="text-red-400">Error: {error}</p>;
  }

  if (!data) {
    return <p className="text-slate-400">Loading insights...</p>;
  }

  const { summary, timeline, top_authors, books_to_revisit, signals } = data;

  return (
    <section className="space-y-8 pb-12">
      <div>
        <p className="text-sm uppercase tracking-wide text-amber-400">Insights</p>
        <h1 className="text-3xl font-semibold mt-2">Reading memory at a glance</h1>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Total Books" value={summary.books} />
        <Metric label="Total Highlights" value={summary.highlights} />
        <Metric label="Imports" value={summary.imports} />
      </div>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Highlighting Activity</h2>
        <div className="rounded border border-slate-800 bg-slate-900 p-6 flex items-end gap-2 h-64 overflow-x-auto pt-10">
          {timeline.length === 0 ? (
            <p className="text-slate-400 m-auto">No timeline data available.</p>
          ) : (
            timeline.map((item) => {
              const maxCount = Math.max(...timeline.map((t) => t.count));
              const height = Math.max((item.count / maxCount) * 100, 5);
              return (
                <div key={item.month} className="flex flex-col items-center gap-2 group relative flex-1 min-w-[2.5rem]">
                  <div className="absolute -top-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-800 text-xs px-2 py-1 rounded text-slate-200 whitespace-nowrap z-10 pointer-events-none">
                    {item.count} highlights
                  </div>
                  <div className="w-full bg-amber-500/80 rounded-t transition-all group-hover:bg-amber-400" style={{ height: `${height}%` }} />
                  <span className="text-xs text-slate-500 whitespace-nowrap mt-2">{item.month}</span>
                </div>
              );
            })
          )}
        </div>
      </section>

      <div className="grid gap-8 lg:grid-cols-2">
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Authors you return to</h2>
          <div className="rounded border border-slate-800 bg-slate-900">
            {top_authors.length === 0 ? (
              <p className="p-4 text-slate-400">No authors yet.</p>
            ) : (
              top_authors.map((author) => (
                <div key={author.name} className="border-t border-slate-800 p-4 first:border-t-0 flex justify-between items-center">
                  <p className="font-medium text-slate-200">{author.name}</p>
                  <p className="text-sm text-slate-400">
                    {author.total_books} books · {author.total_highlights} highlights
                  </p>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Books worth revisiting</h2>
          <div className="rounded border border-slate-800 bg-slate-900">
            {books_to_revisit.length === 0 ? (
              <p className="p-4 text-slate-400">No books yet.</p>
            ) : (
              books_to_revisit.map((book) => (
                <div key={book.id} className="border-t border-slate-800 p-4 first:border-t-0">
                  <p className="font-medium text-slate-200">{book.title}</p>
                  <p className="text-sm text-slate-400 mt-1">
                    {book.author ?? 'Unknown author'} · {book.total_highlights} highlights
                  </p>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Habit Signals</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded border border-slate-800 bg-slate-900 p-4 flex justify-between items-center">
            <span className="text-slate-400">Seen in Spark</span>
            <span className="text-2xl font-semibold text-slate-200">{signals.seen}</span>
          </div>
          <div className="rounded border border-slate-800 bg-slate-900 p-4 flex justify-between items-center">
            <span className="text-slate-400">Favorited</span>
            <span className="text-2xl font-semibold text-amber-400">{signals.favorites}</span>
          </div>
          <div className="rounded border border-slate-800 bg-slate-900 p-4 flex justify-between items-center">
            <span className="text-slate-400">Hidden</span>
            <span className="text-2xl font-semibold text-slate-500">{signals.hidden}</span>
          </div>
        </div>
      </section>

      <section className="space-y-4 pt-8 border-t border-slate-800">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Sparkles className="text-amber-400" />
          AI Discovery: What to read next
        </h2>
        <p className="max-w-2xl text-slate-300 text-sm">
          Discover new books based on your top authors and most highlighted topics. 
          This will securely ping the free Google Gemini API to analyze your reading habits and suggest 3 new books.
        </p>

        {!aiRecs ? (
          <div className="rounded border border-slate-800 bg-slate-900 p-6 flex flex-col items-center justify-center text-center">
            <button
              onClick={() => loadAIRecommendations(false)}
              disabled={loadingAi}
              className="rounded bg-amber-500 px-6 py-3 font-medium text-slate-950 hover:bg-amber-400 disabled:opacity-50 transition-colors inline-flex items-center gap-2"
            >
              {loadingAi ? <RefreshCw size={18} className="animate-spin" /> : <Sparkles size={18} />}
              {loadingAi ? 'Analyzing reading habits...' : 'Discover New Books'}
            </button>
            {aiError && <p className="mt-4 text-sm text-red-400">{aiError}</p>}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex justify-end">
              <button
                onClick={() => loadAIRecommendations(true)}
                disabled={loadingAi}
                className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 transition-colors disabled:opacity-50"
              >
                <RefreshCw size={14} className={loadingAi ? "animate-spin" : ""} />
                {loadingAi ? 'Refreshing...' : 'Refresh Recommendations'}
              </button>
            </div>
            <div className="space-y-8">
              {aiRecs.map((genreGroup, i) => (
                <div key={i} className="space-y-4">
                  <h3 className="text-xl font-semibold flex items-center gap-2 text-slate-200 border-b border-slate-800 pb-2">
                    <Sparkles size={18} className="text-amber-500" />
                    {genreGroup.genre}
                  </h3>
                  <div className="grid gap-4 md:grid-cols-2">
                    {genreGroup.books.map((rec, j) => (
                      <div key={j} className="rounded border border-slate-800 bg-slate-900 p-5 flex flex-col">
                        <h4 className="font-semibold text-lg text-slate-200">{rec.title}</h4>
                        <p className="text-sm text-amber-400 mb-3">{rec.author}</p>
                        <p className="text-sm text-slate-400 flex-1">{rec.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            
            {aiHistory.length > 0 && (
              <div className="mt-8 pt-6 border-t border-slate-800">
                <details className="group">
                  <summary className="flex cursor-pointer items-center gap-2 font-medium text-slate-400 hover:text-slate-200 transition-colors list-none">
                    <History size={16} />
                    <span>View Past Recommendations ({aiHistory.length} generations)</span>
                  </summary>
                  <div className="mt-6 space-y-10 pl-2 border-l-2 border-slate-800">
                    {aiHistory.map((generation) => (
                      <div key={generation.id} className="space-y-4">
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                          {new Date(generation.created_at).toLocaleString()}
                        </p>
                        <div className="space-y-6">
                          {generation.recommendations.map((genreGroup, i) => (
                            <div key={i} className="space-y-3">
                              <h4 className="text-sm font-semibold text-slate-300">
                                {genreGroup.genre}
                              </h4>
                              <div className="grid gap-3 md:grid-cols-2">
                                {genreGroup.books.map((rec, j) => (
                                  <div key={j} className="rounded border border-slate-800/50 bg-slate-900/50 p-4 flex flex-col">
                                    <h5 className="font-semibold text-sm text-slate-300">{rec.title}</h5>
                                    <p className="text-xs text-amber-500 mb-2">{rec.author}</p>
                                    <p className="text-xs text-slate-500 flex-1">{rec.reason}</p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              </div>
            )}
          </div>
        )}
      </section>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-1 text-3xl font-semibold text-slate-200">{value}</p>
    </div>
  );
}
