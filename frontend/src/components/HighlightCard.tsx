import { Link } from 'react-router-dom';
import { Eye, EyeOff, Star } from 'lucide-react';
import SourceBadge from './SourceBadge';

type HighlightCardData = {
  id: string;
  content: string;
  note?: string | null;
  page?: number | null;
  location_start?: number | null;
  location_end?: number | null;
  date_added?: string | null;
  source: string;
  is_favorite?: boolean;
  is_hidden?: boolean;
};

type Props = {
  highlight: HighlightCardData;
  bookTitle?: string;
  bookAuthor?: string | null;
  bookHref?: string;
  onToggleFavorite?: () => void;
  onToggleHidden?: () => void;
};

export default function HighlightCard({ highlight, bookTitle, bookAuthor, bookHref, onToggleFavorite, onToggleHidden }: Props) {
  return (
    <article className="rounded border border-slate-800 bg-slate-900 p-5">
      {highlight.content ? (
        <blockquote className="font-serif text-xl leading-relaxed text-slate-100">{highlight.content}</blockquote>
      ) : (
        <p className="text-slate-400">Note</p>
      )}
      {highlight.note ? <p className="mt-4 text-sm text-amber-100">Note: {highlight.note}</p> : null}

      {bookTitle ? (
        <p className="mt-4 text-sm text-slate-400">
          {bookHref ? (
            <Link to={bookHref} className="text-slate-200 hover:text-amber-300">
              {bookTitle}
            </Link>
          ) : (
            <span className="text-slate-200">{bookTitle}</span>
          )}
          {bookAuthor ? ` · ${bookAuthor}` : ''}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
        <SourceBadge source={highlight.source} />
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

      {(onToggleFavorite || onToggleHidden) && (
        <div className="mt-4 flex gap-2">
          {onToggleFavorite ? (
            <button
              type="button"
              onClick={onToggleFavorite}
              className="inline-flex h-8 items-center gap-1.5 rounded bg-slate-800 px-2.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
            >
              <Star size={14} className={highlight.is_favorite ? 'fill-amber-400 text-amber-400' : ''} />
              {highlight.is_favorite ? 'Favorited' : 'Favorite'}
            </button>
          ) : null}
          {onToggleHidden ? (
            <button
              type="button"
              onClick={onToggleHidden}
              className="inline-flex h-8 items-center gap-1.5 rounded bg-slate-800 px-2.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
            >
              {highlight.is_hidden ? <Eye size={14} /> : <EyeOff size={14} />}
              {highlight.is_hidden ? 'Unhide' : 'Hide'}
            </button>
          ) : null}
        </div>
      )}
    </article>
  );
}
