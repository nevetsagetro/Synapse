import { useEffect, useState } from 'react';
import { Eye, Star } from 'lucide-react';
import { getFavoriteHighlights, getHiddenHighlights, unfavoriteHighlight, unhideHighlight } from '../api';
import type { HighlightWithBook } from '../types';
import HighlightCard from '../components/HighlightCard';

type Tab = 'favorites' | 'hidden';

export default function FavoritesPage() {
  const [tab, setTab] = useState<Tab>('favorites');
  const [favorites, setFavorites] = useState<HighlightWithBook[]>([]);
  const [hidden, setHidden] = useState<HighlightWithBook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      const [favs, hid] = await Promise.all([getFavoriteHighlights(), getHiddenHighlights()]);
      setFavorites(favs);
      setHidden(hid);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load highlights.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleUnfavorite(id: string) {
    await unfavoriteHighlight(id);
    setFavorites((prev) => prev.filter((h) => h.id !== id));
  }

  async function handleUnhide(id: string) {
    await unhideHighlight(id);
    setHidden((prev) => prev.filter((h) => h.id !== id));
  }

  const items = tab === 'favorites' ? favorites : hidden;

  return (
    <section className="space-y-6">
      <p className="text-sm uppercase tracking-wide text-amber-400">Saved</p>
      <h1 className="text-3xl font-semibold">Favorites &amp; hidden highlights</h1>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setTab('favorites')}
          className={`inline-flex h-10 items-center gap-2 rounded px-3 text-sm font-medium transition ${
            tab === 'favorites' ? 'bg-slate-100 text-slate-950' : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
          }`}
        >
          <Star size={16} className={tab === 'favorites' ? 'fill-amber-500 text-amber-500' : ''} />
          Favorites ({favorites.length})
        </button>
        <button
          type="button"
          onClick={() => setTab('hidden')}
          className={`inline-flex h-10 items-center gap-2 rounded px-3 text-sm font-medium transition ${
            tab === 'hidden' ? 'bg-slate-100 text-slate-950' : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
          }`}
        >
          <Eye size={16} />
          Hidden ({hidden.length})
        </button>
      </div>

      {error ? <div className="rounded border border-red-800 bg-red-950 p-4 text-sm text-red-100">{error}</div> : null}

      {!loading && items.length === 0 ? (
        <div className="rounded border border-slate-800 bg-slate-900 p-6 text-slate-400">
          {tab === 'favorites'
            ? "No favorites yet — star a highlight from Spark or a book's page to save it here."
            : 'Nothing hidden. Hidden highlights stop appearing in Daily Spark until you unhide them.'}
        </div>
      ) : (
        <div className="grid gap-4">
          {items.map((highlight) => (
            <HighlightCard
              key={highlight.id}
              highlight={highlight}
              bookTitle={highlight.book_title}
              bookAuthor={highlight.author}
              bookHref={`/books/${highlight.book_id}`}
              onToggleFavorite={tab === 'favorites' ? () => handleUnfavorite(highlight.id) : undefined}
              onToggleHidden={tab === 'hidden' ? () => handleUnhide(highlight.id) : undefined}
            />
          ))}
        </div>
      )}
    </section>
  );
}
