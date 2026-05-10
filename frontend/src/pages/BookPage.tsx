import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getBook } from '../api';
import type { Book, Highlight } from '../types';

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

  return (
    <section className="space-y-6">
      <p className="text-sm uppercase tracking-wide text-amber-400">Book</p>
      {error ? <div className="rounded border border-red-800 bg-red-950 p-4 text-sm text-red-100">{error}</div> : null}
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold">{book?.title ?? 'Book details'}</h1>
        <p className="text-slate-400">{book?.author ?? 'Unknown author'}</p>
      </div>

      <div className="space-y-4">
        {highlights.length === 0 ? (
          <div className="rounded border border-slate-800 bg-slate-900 p-6 text-slate-400">No highlights found.</div>
        ) : (
          highlights.map((highlight) => (
            <article key={highlight.id} className="rounded border border-slate-800 bg-slate-900 p-5">
              {highlight.content ? (
                <blockquote className="font-serif text-xl leading-relaxed text-slate-100">{highlight.content}</blockquote>
              ) : (
                <p className="text-slate-400">Note</p>
              )}
              {highlight.note ? <p className="mt-4 text-sm text-amber-100">Note: {highlight.note}</p> : null}
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-400">
                {highlight.page ? <span>Page {highlight.page}</span> : null}
                {highlight.location_start ? (
                  <span>
                    Location {highlight.location_start}
                    {highlight.location_end && highlight.location_end !== highlight.location_start
                      ? `-${highlight.location_end}`
                      : ''}
                  </span>
                ) : null}
                {highlight.date_added ? <span>Quoted {highlight.date_added.slice(0, 10)}</span> : null}
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
