import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { favoriteHighlight, getBook, hideHighlight, unfavoriteHighlight, unhideHighlight } from '../api';
import type { Book, Highlight } from '../types';
import HighlightCard from '../components/HighlightCard';

export default function BookPage() {
  const { bookId } = useParams();
  const [book, setBook] = useState<Book | null>(null);
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!bookId) return;
    getBook(bookId)
      .then((data) => {
        setBook(data.book);
        setHighlights(data.highlights);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load book.'));
  }, [bookId]);

  async function toggleFavorite(highlight: Highlight) {
    const updated = highlight.is_favorite ? await unfavoriteHighlight(highlight.id) : await favoriteHighlight(highlight.id);
    setHighlights((prev) => prev.map((h) => (h.id === highlight.id ? { ...h, is_favorite: updated.is_favorite } : h)));
  }

  async function toggleHidden(highlight: Highlight) {
    const updated = highlight.is_hidden ? await unhideHighlight(highlight.id) : await hideHighlight(highlight.id);
    setHighlights((prev) => prev.map((h) => (h.id === highlight.id ? { ...h, is_hidden: updated.is_hidden } : h)));
  }

  return (
    <section className="space-y-6">
      <p className="text-sm uppercase tracking-wide text-amber-400">Book</p>
      {error ? <div className="rounded border border-red-800 bg-red-950 p-4 text-sm text-red-100">{error}</div> : null}
      <div className="flex items-center gap-4">
        {book?.cover_url ? (
          <img
            src={book.cover_url}
            alt=""
            className="h-24 w-16 shrink-0 rounded object-cover shadow"
          />
        ) : null}
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold">{book?.title ?? 'Book details'}</h1>
          <p className="text-slate-400">{book?.author ?? 'Unknown author'}</p>
        </div>
      </div>

      <div className="space-y-4">
        {highlights.length === 0 ? (
          <div className="rounded border border-slate-800 bg-slate-900 p-6 text-slate-400">No highlights found.</div>
        ) : (
          highlights.map((highlight) => (
            <HighlightCard
              key={highlight.id}
              highlight={highlight}
              onToggleFavorite={() => toggleFavorite(highlight)}
              onToggleHidden={() => toggleHidden(highlight)}
            />
          ))
        )}
      </div>
    </section>
  );
}
