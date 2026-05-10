import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Search, Download } from 'lucide-react';
import { getBooks } from '../api';
import type { Book } from '../types';

export default function LibraryPage() {
  const [books, setBooks] = useState<Book[]>([]);
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  
  const apiUrl = import.meta.env.VITE_API_URL ?? '';

  useEffect(() => {
    getBooks()
      .then(setBooks)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load books.'));
  }, []);

  const filtered = books.filter((book) => {
    const haystack = `${book.title} ${book.author ?? ''}`.toLowerCase();
    return haystack.includes(query.toLowerCase());
  });

  return (
    <section className="space-y-6">
      <p className="text-sm uppercase tracking-wide text-amber-400">Library</p>
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold">Your books</h1>
          <p className="max-w-2xl text-slate-300">Browse imported Kindle books and open their highlights.</p>
        </div>
        <label className="relative block w-full md:w-80">
          <Search className="pointer-events-none absolute left-3 top-3 text-slate-500" size={18} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search books"
            className="h-11 w-full rounded border border-slate-800 bg-slate-900 pl-10 pr-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-amber-500"
          />
        </label>
      </div>
      
      <div className="flex flex-wrap gap-3">
        <a 
          href={`${apiUrl}/api/export/json`}
          className="inline-flex h-9 items-center gap-2 rounded border border-slate-700 bg-slate-800 px-3 text-xs font-medium text-slate-200 transition hover:bg-slate-700"
        >
          <Download size={14} /> JSON
        </a>
        <a 
          href={`${apiUrl}/api/export/csv`}
          className="inline-flex h-9 items-center gap-2 rounded border border-slate-700 bg-slate-800 px-3 text-xs font-medium text-slate-200 transition hover:bg-slate-700"
        >
          <Download size={14} /> CSV
        </a>
        <a 
          href={`${apiUrl}/api/export/sqlite`}
          className="inline-flex h-9 items-center gap-2 rounded border border-slate-700 bg-slate-800 px-3 text-xs font-medium text-slate-200 transition hover:bg-slate-700"
        >
          <Download size={14} /> SQLite DB
        </a>
      </div>

      {error ? <div className="rounded border border-red-800 bg-red-950 p-4 text-sm text-red-100">{error}</div> : null}

      {filtered.length === 0 ? (
        <div className="rounded border border-slate-800 bg-slate-900 p-6 text-slate-400">
          {books.length === 0 ? 'No books imported yet.' : 'No books match your search.'}
        </div>
      ) : (
        <div className="grid gap-3">
          {filtered.map((book) => (
            <Link
              key={book.id}
              to={`/books/${book.id}`}
              className="flex items-center justify-between gap-4 rounded border border-slate-800 bg-slate-900 p-4 transition hover:border-slate-600 hover:bg-slate-900/80"
            >
              <span className="flex min-w-0 items-center gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded bg-slate-800 text-amber-400">
                  <BookOpen size={19} />
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-medium text-slate-100">{book.title}</span>
                  <span className="block truncate text-sm text-slate-400">{book.author ?? 'Unknown author'}</span>
                </span>
              </span>
              <span className="shrink-0 text-sm text-slate-300">{book.total_highlights} highlights</span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
