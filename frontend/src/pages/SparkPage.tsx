import { useEffect, useState } from 'react';
import { Copy, Eye, EyeOff, Flame, RefreshCw, Star, Sparkles, Send } from 'lucide-react';
import {
  favoriteHighlight,
  getOnThisDay,
  getSpark,
  getSparkStreak,
  hideHighlight,
  markSparkSeen,
  unfavoriteHighlight,
  unhideHighlight,
  getRelatedHighlights,
  addThought,
} from '../api';
import type { HighlightWithBook, SparkHighlight, RelatedHighlight, SparkStreak, Thought } from '../types';
import SourceBadge, { sourceLabel } from '../components/SourceBadge';
import HighlightCard from '../components/HighlightCard';

export default function SparkPage() {
  const [highlight, setHighlight] = useState<SparkHighlight | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [related, setRelated] = useState<RelatedHighlight[]>([]);
  const [loadingRelated, setLoadingRelated] = useState(false);
  const [newThought, setNewThought] = useState('');
  const [savingThought, setSavingThought] = useState(false);
  const [streak, setStreak] = useState<SparkStreak | null>(null);
  const [onThisDay, setOnThisDay] = useState<HighlightWithBook[]>([]);

  async function refresh() {
    setLoading(true);
    setRelated([]);
    const result = await getSpark();
    setHighlight(result.highlight);
    setLoading(false);

    getSparkStreak().then(setStreak).catch(() => setStreak(null));
    getOnThisDay().then(setOnThisDay).catch(() => setOnThisDay([]));

    if (result.highlight) {
      setLoadingRelated(true);
      try {
        const relatedRes = await getRelatedHighlights(result.highlight.id);
        setRelated(relatedRes);
      } catch (e) {
        console.error("Failed to load related highlights", e);
      } finally {
        setLoadingRelated(false);
      }
    }
  }

  async function markSeen() {
    if (!highlight) return;
    const result = await markSparkSeen(highlight.id);
    setHighlight({ ...highlight, last_seen_at: result.last_seen_at });
    setMessage('Marked as seen.');
  }

  async function toggleFavorite() {
    if (!highlight) return;
    const result = highlight.is_favorite
      ? await unfavoriteHighlight(highlight.id)
      : await favoriteHighlight(highlight.id);
    setHighlight({ ...highlight, is_favorite: result.is_favorite });
    setMessage(result.is_favorite ? 'Added to favorites.' : 'Removed from favorites.');
  }

  async function hideCurrent() {
    if (!highlight) return;
    await hideHighlight(highlight.id);
    setMessage('Hidden from future Spark results.');
    await refresh();
  }

  function copyObsidianQuote() {
    if (!highlight) return;
    const lines = [];

    let titleLine = "> [!quote]";
    if (highlight.book_title) {
      titleLine += ` ${highlight.book_title}`;
      if (highlight.quoted_at) {
        titleLine += ` - ${highlight.quoted_at.slice(0, 10)}`;
      }
    }
    lines.push(titleLine);

    const textToQuote = highlight.content || highlight.note || "";
    for (const paragraph of textToQuote.split('\n')) {
      lines.push(`> ${paragraph}`);
    }

    // Source attribution line
    const attribution = sourceLabel((highlight as any).source);
    if (attribution) {
      lines.push(`> `);
      lines.push(`> — *${attribution}*`);
    }
    
    navigator.clipboard.writeText(lines.join('\n')).then(() => {
      setMessage('Copied Obsidian format to clipboard.');
    }).catch(() => {
      setMessage('Failed to copy to clipboard.');
    });
  }

  async function submitThought() {
    if (!highlight || !newThought.trim()) return;
    setSavingThought(true);
    try {
      const savedThought = await addThought(highlight.id, newThought.trim());
      setHighlight({
        ...highlight,
        thoughts: [...(highlight.thoughts || []), savedThought]
      });
      setNewThought('');
      setMessage('Thought saved.');
    } catch (e) {
      console.error("Failed to save thought", e);
      setMessage('Failed to save thought.');
    } finally {
      setSavingThought(false);
    }
  }

  useEffect(() => {
    refresh().catch(() => setLoading(false));
  }, []);

  async function toggleOnThisDayFavorite(item: HighlightWithBook) {
    const updated = item.is_favorite ? await unfavoriteHighlight(item.id) : await favoriteHighlight(item.id);
    setOnThisDay((prev) => prev.map((h) => (h.id === item.id ? { ...h, is_favorite: updated.is_favorite } : h)));
  }

  async function toggleOnThisDayHidden(item: HighlightWithBook) {
    const updated = item.is_hidden ? await unhideHighlight(item.id) : await hideHighlight(item.id);
    setOnThisDay((prev) => prev.filter((h) => h.id !== item.id || !updated.is_hidden));
  }

  return (
    <section className="space-y-5">
      <p className="text-sm uppercase tracking-wide text-amber-400">Daily Spark</p>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold">One remembered idea, every day</h1>
          {streak && streak.current_streak > 0 ? (
            <p className="inline-flex items-center gap-1.5 text-sm font-medium text-amber-400">
              <Flame size={16} className="fill-amber-400" />
              {streak.current_streak} day{streak.current_streak === 1 ? '' : 's'} in a row
              {streak.longest_streak > streak.current_streak ? (
                <span className="text-slate-500">· best {streak.longest_streak}</span>
              ) : null}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={refresh}
          className="inline-flex h-10 items-center gap-2 rounded bg-slate-100 px-3 text-sm font-semibold text-slate-950"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>
      <div className="max-w-3xl rounded border border-slate-800 bg-slate-900 p-6">
        {highlight ? (
          <>
            <blockquote className="font-serif text-2xl leading-relaxed text-slate-100">
              {highlight.content || highlight.note}
            </blockquote>
            <p className="mt-5 text-sm text-slate-400">
              {highlight.book_title}
              {highlight.author ? ` · ${highlight.author}` : ''}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {(highlight as any).source && <SourceBadge source={(highlight as any).source} />}
              {highlight.quoted_at ? (
                <p className="text-xs text-slate-500">Quoted {highlight.quoted_at.slice(0, 10)}</p>
              ) : null}
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={markSeen}
                className="inline-flex h-10 items-center gap-2 rounded bg-slate-800 px-3 text-sm font-medium text-slate-100 hover:bg-slate-700"
              >
                <Eye size={16} />
                Seen
              </button>
              <button
                type="button"
                onClick={toggleFavorite}
                className="inline-flex h-10 items-center gap-2 rounded bg-slate-800 px-3 text-sm font-medium text-slate-100 hover:bg-slate-700"
              >
                <Star size={16} className={highlight.is_favorite ? 'fill-amber-400 text-amber-400' : ''} />
                {highlight.is_favorite ? 'Favorited' : 'Favorite'}
              </button>
              <button
                type="button"
                onClick={hideCurrent}
                className="inline-flex h-10 items-center gap-2 rounded bg-slate-800 px-3 text-sm font-medium text-slate-100 hover:bg-slate-700"
              >
                <EyeOff size={16} />
                Hide
              </button>
              <button
                type="button"
                onClick={copyObsidianQuote}
                className="inline-flex h-10 items-center gap-2 rounded bg-slate-800 px-3 text-sm font-medium text-slate-100 hover:bg-slate-700"
              >
                <Copy size={16} />
                Copy Obsidian
              </button>
            </div>
            {highlight.last_seen_at ? (
              <p className="mt-3 text-xs text-slate-500">Seen {new Date(highlight.last_seen_at).toLocaleString()}</p>
            ) : null}
          </>
        ) : (
          <blockquote className="font-serif text-2xl leading-relaxed text-slate-100">
            Import your Kindle highlights to start resurfacing the ideas worth returning to.
          </blockquote>
        )}
      </div>
      {message ? <p className="text-sm text-emerald-300">{message}</p> : null}

      {/* Personal Thoughts Section */}
      {highlight && (
        <div className="max-w-3xl space-y-4">
          <div className="rounded border border-slate-800 bg-slate-900 p-4">
            <h3 className="text-sm font-medium text-slate-300 mb-2">What are you thinking about this quote?</h3>
            <div className="flex flex-col gap-3">
              <textarea
                value={newThought}
                onChange={(e) => setNewThought(e.target.value)}
                placeholder="Write your reflection here..."
                className="w-full rounded border border-slate-800 bg-slate-950 p-3 text-sm text-slate-200 outline-none placeholder:text-slate-600 focus:border-amber-500 min-h-[80px]"
              />
              <div className="flex justify-end">
                <button
                  onClick={submitThought}
                  disabled={savingThought || !newThought.trim()}
                  className="inline-flex h-9 items-center gap-2 rounded bg-amber-500 px-4 text-sm font-semibold text-slate-950 hover:bg-amber-400 disabled:opacity-50 transition-colors"
                >
                  {savingThought ? <RefreshCw size={14} className="animate-spin" /> : <Send size={14} />}
                  Save Thought
                </button>
              </div>
            </div>
            
            {highlight.thoughts && highlight.thoughts.length > 0 && (
              <div className="mt-6 space-y-3 pt-4 border-t border-slate-800">
                {highlight.thoughts.map(thought => (
                  <div key={thought.id} className="bg-slate-950 p-3 rounded border border-slate-800">
                    <p className="text-sm text-slate-200 whitespace-pre-wrap">{thought.content}</p>
                    <p className="text-xs text-slate-500 mt-2">{new Date(thought.created_at).toLocaleString()}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Related Highlights Section */}
      {related.length > 0 && (
        <div className="mt-8 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Sparkles size={18} className="text-amber-400" />
            Related Ideas
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {related.map((item) => (
              <div key={item.id} className="rounded border border-slate-800 bg-slate-900 p-5 flex flex-col justify-between">
                <blockquote className="font-serif text-lg leading-relaxed text-slate-200">
                  {item.content}
                </blockquote>
                <p className="mt-4 text-xs text-slate-400">
                  {item.book_title}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* On This Day Section */}
      {onThisDay.length > 0 && (
        <div className="mt-8 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Sparkles size={18} className="text-amber-400" />
            On this day
          </h2>
          <div className="grid gap-4">
            {onThisDay.map((item) => (
              <HighlightCard
                key={item.id}
                highlight={item}
                bookTitle={item.book_title}
                bookAuthor={item.author}
                bookHref={`/books/${item.book_id}`}
                onToggleFavorite={() => toggleOnThisDayFavorite(item)}
                onToggleHidden={() => toggleOnThisDayHidden(item)}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
