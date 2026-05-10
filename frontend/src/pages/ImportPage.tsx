import { useEffect, useState } from 'react';
import { FileText, RefreshCw, Upload, Sparkles } from 'lucide-react';
import { getImports, getSummary, importDefaultClippings, uploadClippings, backfillEmbeddings, getEmbeddingStatus } from '../api';
import type { ImportLog, ImportSummary, Summary } from '../types';

export default function ImportPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [imports, setImports] = useState<ImportLog[]>([]);
  const [importResult, setImportResult] = useState<ImportSummary | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [missingEmbeddings, setMissingEmbeddings] = useState<number | null>(null);
  const [embeddingError, setEmbeddingError] = useState<string | null>(null);

  async function refresh() {
    const [nextSummary, nextImports] = await Promise.all([getSummary(), getImports()]);
    setSummary(nextSummary);
    setImports(nextImports);
  }

  async function fetchEmbeddingStatus() {
    try {
      const status = await getEmbeddingStatus();
      setMissingEmbeddings(status.missing);
    } catch (e) {
      console.error("Failed to fetch embedding status", e);
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(readError(err)));
    fetchEmbeddingStatus();
  }, []);

  async function runImport() {
    setBusy('import');
    setError(null);
    setImportResult(null);
    try {
      const result = await importDefaultClippings();
      setImportResult(result);
      await refresh();
    } catch (err) {
      setError(readError(err));
    } finally {
      setBusy(null);
    }
  }

  async function runUploadImport() {
    if (!selectedFile) {
      setError('Choose a My Clippings.txt file first.');
      return;
    }

    setBusy('upload');
    setError(null);
    setImportResult(null);
    try {
      const result = await uploadClippings(selectedFile);
      setImportResult(result);
      await refresh();
      await fetchEmbeddingStatus();
    } catch (err) {
      setError(readError(err));
    } finally {
      setBusy(null);
    }
  }

  async function runBackfill() {
    setBusy('backfill');
    setEmbeddingError(null);
    try {
      const res = await backfillEmbeddings();
      if (res.error) {
        setEmbeddingError(res.error);
      }
      await fetchEmbeddingStatus();
    } catch (err) {
      setEmbeddingError(readError(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="space-y-6">
      <p className="text-sm uppercase tracking-wide text-amber-400">Import</p>
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold">Bring in My Clippings.txt</h1>
        <p className="max-w-2xl text-slate-300">
          Load a Kindle clipping file and store it locally.
        </p>
      </div>

      {error ? <Status tone="error">{error}</Status> : null}

      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Books" value={summary?.books ?? 0} />
        <Metric label="Highlights" value={summary?.highlights ?? 0} />
        <Metric label="Imports" value={summary?.imports ?? 0} />
      </div>

      <div className="space-y-3 rounded border border-slate-800 bg-slate-900 p-4">
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-200">My Clippings.txt</span>
          <input
            type="file"
            accept=".txt,text/plain"
            onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            className="block w-full rounded border border-slate-700 bg-slate-950 p-2 text-sm text-slate-300 file:mr-3 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-slate-950"
          />
        </label>
        <button
          type="button"
          onClick={runUploadImport}
          disabled={busy !== null}
          className="inline-flex h-11 items-center gap-2 rounded bg-amber-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy === 'upload' ? <RefreshCw size={17} className="animate-spin" /> : <Upload size={17} />}
          Upload and import
        </button>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={runImport}
          disabled={busy !== null}
          className="inline-flex h-11 items-center gap-2 rounded bg-slate-800 px-4 text-sm font-semibold text-slate-100 transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy === 'import' ? <RefreshCw size={17} className="animate-spin" /> : <Upload size={17} />}
          Import default file
        </button>
      </div>

      {importResult ? (
        <Status tone="success">
          Import complete: {importResult.records_created} created, {importResult.records_skipped} skipped,
          {` ${importResult.records_failed}`} failed.
        </Status>
      ) : null}


      <div className="space-y-3">
        <h2 className="text-lg font-semibold">Recent imports</h2>
        <div className="overflow-hidden rounded border border-slate-800">
          {imports.length === 0 ? (
            <div className="flex items-center gap-3 p-4 text-slate-400">
              <FileText size={18} />
              No imports yet.
            </div>
          ) : (
            imports.map((item) => (
              <div key={item.id} className="border-t border-slate-800 p-4 first:border-t-0">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium text-slate-100">{item.file_name ?? item.source}</p>
                  <p className="text-xs text-slate-400">{new Date(item.created_at).toLocaleString()}</p>
                </div>
                <p className="mt-2 text-sm text-slate-300">
                  Seen {item.records_seen}, created {item.records_created}, skipped {item.records_skipped}, failed{' '}
                  {item.records_failed}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="space-y-3 pt-6 border-t border-slate-800">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Sparkles size={18} className="text-amber-400" />
          Semantic Search Setup
        </h2>
        <p className="max-w-2xl text-slate-300 text-sm">
          To enable AI-powered "Related Ideas", Synapse needs to generate embeddings for your highlights using Google Gemini.
          This will securely send your highlights to Google's API via the generous free tier.
        </p>
        <div className="rounded border border-slate-800 bg-slate-900 p-4 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
          <div>
            <p className="font-medium text-slate-200">Embedding Backfill</p>
            {missingEmbeddings !== null && (
              <p className="text-sm text-slate-400 mt-1">
                {missingEmbeddings > 0 
                  ? `${missingEmbeddings} highlights are missing embeddings.` 
                  : 'All highlights have embeddings!'}
              </p>
            )}
            {embeddingError && <p className="text-sm text-red-400 mt-2">{embeddingError}</p>}
          </div>

          <button
            onClick={runBackfill}
            disabled={busy !== null || missingEmbeddings === 0 || missingEmbeddings === null}
            className="rounded bg-slate-800 px-4 py-2 font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-50 transition-colors inline-flex items-center gap-2"
          >
            {busy === 'backfill' ? <RefreshCw size={16} className="animate-spin" /> : null}
            Generate Embeddings
          </button>
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-1 text-3xl font-semibold">{value}</p>
    </div>
  );
}

function Status({ tone, children }: { tone: 'success' | 'error'; children: React.ReactNode }) {
  const color = tone === 'success' ? 'border-emerald-800 bg-emerald-950 text-emerald-100' : 'border-red-800 bg-red-950 text-red-100';
  return <div className={`rounded border p-4 text-sm ${color}`}>{children}</div>;
}

function readError(error: unknown) {
  if (typeof error === 'object' && error && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    return response?.data?.detail ?? 'Request failed.';
  }
  return error instanceof Error ? error.message : 'Request failed.';
}
