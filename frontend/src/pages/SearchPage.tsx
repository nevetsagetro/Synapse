import { useEffect, useState } from 'react';
import { Search as SearchIcon } from 'lucide-react';
import { favoriteHighlight, hideHighlight, searchHighlights, unfavoriteHighlight, unhideHighlight } from '../api';
import type { HighlightWithBook } from '../types';
import HighlightCard from '../components/HighlightCard';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<HighlightWithBook[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setSearched(false);
      return;
    }

    setLoading(true);
    const handle = setTimeout(() => {
      searchHighlights(trimmed)
        .then((data) => {
          setResults(data);
          setSearched(true);
        })
        .finally(() => setLoading(false));
    }, 300);

    return () => clearTimeout(handle);
  }, [query]);

  async function toggleFavorite(highlight: HighlightWithBook) {
    const updated = highlight.is_favorite ? await unfavoriteHighlight(highlight.id) : await favoriteHighlight(highlight.id);
    setResults((prev) => prev.map((h) => (h.id === highlight.id ? { ...h, is_favorite: updated.is_favorite } : h)));
  }

  async function toggleHidden(highlight: HighlightWithBook) {
    const updated = highlight.is_hidden ? await unhideHighlight(highlight.id) : await hideHighlight(highlight.id);
    setResults((prev) => prev.map((h) => (h.id === highlight.id ? { ...h, is_hidden: updated.is_hidden } : h)));
  }

  return (
    <section className="space-y-6">
      <p className="text-sm uppercase tracking-wide text-amber-400">Search</p>
      <h1 className="text-3xl font-semibold">Find a highlight</h1>

      <label className="relative block max-w-xl">
        <SearchIcon className="pointer-events-none absolute left-3 top-3.5 text-slate-500" size={18} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search across everything you've highlighted"
          autoFocus
          className="h-12 w-full rounded border border-slate-800 bg-slate-900 pl-10 pr-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-amber-500"
        />
      </label>

      {loading ? <p className="text-sm text-slate-400">Searching…</p> : null}

      {!loading && searched && results.length === 0 ? (
        <div className="rounded border border-slate-800 bg-slate-900 p-6 text-slate-400">
          No highlights match "{query.trim()}".
        </div>
      ) : null}

      <div className="grid gap-4">
        {results.map((highlight) => (
          <HighlightCard
            key={highlight.id}
            highlight={highlight}
            bookTitle={highlight.book_title}
            bookAuthor={highlight.author}
            bookHref={`/books/${highlight.book_id}`}
            onToggleFavorite={() => toggleFavorite(highlight)}
            onToggleHidden={() => toggleHidden(highlight)}
          />
        ))}
      </div>
    </section>
  );
}
