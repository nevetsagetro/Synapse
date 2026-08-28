const SOURCE_LABELS: Record<string, { label: string; className: string }> = {
  my_clippings: {
    label: 'Kindle Clippings',
    className: 'bg-amber-900/40 text-amber-300 border border-amber-800/50',
  },
  kindle_notebook: {
    label: 'Kindle Notebook',
    className: 'bg-sky-900/40 text-sky-300 border border-sky-800/50',
  },
};

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source]?.label ?? source;
}

export default function SourceBadge({ source }: { source: string }) {
  const config = SOURCE_LABELS[source] ?? {
    label: source,
    className: 'bg-slate-800 text-slate-400 border border-slate-700',
  };
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  );
}
