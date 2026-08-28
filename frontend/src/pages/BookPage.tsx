import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { BookOpen, Pencil, X } from 'lucide-react';
import { favoriteHighlight, getBook, hideHighlight, setBookCover, unfavoriteHighlight, unhideHighlight } from '../api';
import type { Book, Highlight } from '../types';
import HighlightCard from '../components/HighlightCard';

export default function BookPage() {
  const { bookId } = useParams();
  const [book, setBook] = useState<Book | null>(null);
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editingCover, setEditingCover] = useState(false);
  const [coverUrlInput, setCoverUrlInput] = useState('');
  const [savingCover, setSavingCover] = useState(false);

  useEffect(() => {
    if (!bookId) return;
    getBook(bookId)
      .then((data) => {
        setBook(data.book);
        setHighlights(data.highlights);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load book.'));
  }, [bookId]);

  function startEditingCover() {
    setCoverUrlInput(book?.cover_url ?? '');
    setEditingCover(true);
  }

  async function saveCover() {
    if (!book) return;
    setSavingCover(true);
    try {
      const result = await setBookCover(book.id, coverUrlInput.trim() || null);
      setBook({ ...book, cover_url: result.cover_url });
      setEditingCover(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save cover.');
    } finally {
      setSavingCover(false);
    }
  }

  async function removeCover() {
    if (!book) return;
    setSavingCover(true);
    try {
      const result = await setBookCover(book.id, null);
      setBook({ ...book, cover_url: result.cover_url });
      setEditingCover(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove cover.');
    } finally {
      setSavingCover(false);
    }
  }

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
      <div className="flex items-start gap-4">
        <div className="group relative h-24 w-16 shrink-0">
          {book?.cover_url ? (
            <img src={book.cover_url} alt="" className="h-24 w-16 rounded object-cover shadow" />
          ) : (
            <div className="grid h-24 w-16 place-items-center rounded bg-slate-800 text-amber-400">
              <BookOpen size={24} />
            </div>
          )}
          {book ? (
            <button
              type="button"
              onClick={startEditingCover}
              title="Edit cover"
              className="absolute inset-0 hidden items-center justify-center rounded bg-slate-950/70 text-slate-100 group-hover:flex"
            >
              <Pencil size={18} />
            </button>
          ) : null}
        </div>
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold">{book?.title ?? 'Book details'}</h1>
          <p className="text-slate-400">{book?.author ?? 'Unknown author'}</p>
        </div>
      </div>

      {editingCover ? (
        <div className="max-w-md space-y-2 rounded border border-slate-800 bg-slate-900 p-4">
          <label className="block text-sm font-medium text-slate-300">Cover image URL</label>
          <input
            value={coverUrlInput}
            onChange={(event) => setCoverUrlInput(event.target.value)}
            placeholder="https://..."
            autoFocus
            className="h-10 w-full rounded border border-slate-800 bg-slate-950 px-3 text-sm text-slate-100 outline-none focus:border-amber-500"
          />
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={saveCover}
              disabled={savingCover}
              className="inline-flex h-9 items-center rounded bg-amber-500 px-3 text-sm font-semibold text-slate-950 hover:bg-amber-400 disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => setEditingCover(false)}
              disabled={savingCover}
              className="inline-flex h-9 items-center gap-1 rounded bg-slate-800 px-3 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-50"
            >
              <X size={14} /> Cancel
            </button>
            {book?.cover_url ? (
              <button
                type="button"
                onClick={removeCover}
                disabled={savingCover}
                className="text-sm text-slate-400 hover:text-red-300 disabled:opacity-50"
              >
                Remove cover
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

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
