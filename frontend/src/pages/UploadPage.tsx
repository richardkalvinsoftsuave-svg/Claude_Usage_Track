import { useState, useRef } from 'react';
import { uploadImage, confirmUpload, reextract } from '../api';
import type { UploadPreviewResponse } from '../types';

const EXTRACTION_METHOD = 'ocr';

export default function UploadPage() {
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<UploadPreviewResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function handleUpload(file: File) {
    if (!file) return;
    setUploading(true);
    setError(null);
    setPreview(null);
    setSaved(false);
    uploadImage(file)
      .then(setPreview)
      .catch((e) => setError(e.message))
      .finally(() => setUploading(false));
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) handleUpload(f);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) handleUpload(f);
  }

  function handleReextract() {
    if (!preview) return;
    setUploading(true);
    setError(null);
    reextract(preview.image_path)
      .then(setPreview)
      .catch((e) => setError(e.message))
      .finally(() => setUploading(false));
  }

  function handleConfirm() {
    const email = preview?.extracted.email;
    if (!preview || !email) return;
    const e = preview.extracted;
    setSaving(true);
    setError(null);
    confirmUpload({
      email: email.trim().toLowerCase(),
      image_path: preview.image_path,
      original_filename: preview.original_filename,
      auth_method: e.auth_method,
      organization: e.organization,
      plan_tier: e.plan_tier,
      weekly_usage_pct: e.weekly_usage_pct,
      weekly_fable_usage_pct: e.weekly_fable_usage_pct,
      weekly_reset_at: e.weekly_reset_at,
      weekly_fable_reset_at: e.weekly_fable_reset_at,
      extraction_method: EXTRACTION_METHOD,
      raw_extracted_text: preview.raw_text,
      was_manually_edited: false,
    })
      .then(() => setSaved(true))
      .catch((err) => setError(err.message))
      .finally(() => setSaving(false));
  }

  function handleReset() {
    setPreview(null);
    setSaved(false);
    setError(null);
    if (fileRef.current) fileRef.current.value = '';
  }

  const canConfirm = Boolean(preview?.extracted.email?.trim());

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Upload Usage Screenshot</h1>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>
      )}

      {!preview && (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-blue-400 transition-colors cursor-pointer"
          onClick={() => fileRef.current?.click()}
        >
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={handleFileChange} className="hidden" />
          {uploading ? (
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              <p className="text-gray-500">Extracting text from image…</p>
            </div>
          ) : (
            <>
              <svg className="mx-auto h-10 w-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
              <p className="mt-2 text-sm text-gray-600">Drop a Claude <code>/usage</code> screenshot here, or click to browse</p>
              <p className="text-xs text-gray-400 mt-1">PNG, JPEG, or WebP — up to 10 MB</p>
            </>
          )}
        </div>
      )}

      {preview && !saved && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Review extracted values</h2>
            <span className="inline-flex items-center rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-medium text-purple-700">OCR</span>
          </div>

          <div className="flex flex-col md:flex-row gap-6">
            <div className="shrink-0">
              <img src={`/uploads/${preview.image_path}`} alt="Uploaded" className="max-w-sm rounded border" />
            </div>

            <div className="flex-1">
              <p className="text-xs text-gray-400 mb-3">
                These values were read automatically and can't be edited here. If something looks wrong, try re-extracting,
                or fix it later from the user's history page.
              </p>

              <dl className="divide-y divide-gray-100">
                <ReadOnlyField label="Auth method" value={preview.extracted.auth_method} />
                <ReadOnlyField label="Email" value={preview.extracted.email} />
                <ReadOnlyField label="Organization" value={preview.extracted.organization} />
                <ReadOnlyField label="Plan" value={preview.extracted.plan_tier} />
                <ReadOnlyField
                  label="Weekly usage"
                  value={preview.extracted.weekly_usage_pct != null ? `${preview.extracted.weekly_usage_pct}%` : null}
                />
                <ReadOnlyField
                  label="Weekly Fable usage"
                  value={preview.extracted.weekly_fable_usage_pct != null ? `${preview.extracted.weekly_fable_usage_pct}%` : null}
                />
                <ReadOnlyField
                  label="Weekly reset"
                  value={formatResetDate(preview.extracted.weekly_reset_at)}
                  locked={preview.weekly_reset_locked}
                />
                <ReadOnlyField
                  label="Fable reset"
                  value={formatResetDate(preview.extracted.weekly_fable_reset_at)}
                  locked={preview.fable_reset_locked}
                />
              </dl>

              {!preview.extracted.email && (
                <p className="mt-3 text-sm text-amber-600">
                  Could not detect an email in this screenshot. Try "Re-extract with AI", or retake the screenshot so the email is visible.
                </p>
              )}

              <div className="flex flex-wrap items-center gap-3 pt-5">
                <button type="button" onClick={handleReextract} disabled={uploading} className="inline-flex items-center rounded-md bg-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-purple-500 disabled:opacity-50">
                  {uploading ? 'Re-extracting…' : 'Re-extract with AI'}
                </button>
                <button type="button" onClick={handleConfirm} disabled={saving || !canConfirm} className="inline-flex rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 disabled:opacity-50">
                  {saving ? 'Saving…' : 'Confirm & Save'}
                </button>
                <button type="button" onClick={handleReset} className="text-sm text-gray-500 hover:text-gray-700">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {saved && (
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <div className="text-green-600 text-lg font-semibold mb-2">✓ Upload saved</div>
          <p className="text-gray-600 mb-4">Usage data has been recorded.</p>
          <button onClick={handleReset} className="inline-flex rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500">Upload another</button>
        </div>
      )}
    </div>
  );
}

function ReadOnlyField({ label, value, locked }: { label: string; value: string | null | undefined; locked?: boolean }) {
  return (
    <div className="grid grid-cols-[160px_1fr] items-center gap-3 py-2 text-sm">
      <dt className="font-medium text-gray-500">{label}</dt>
      <dd className="flex items-center gap-2 text-gray-900">
        {value ? value : <span className="text-gray-300">—</span>}
        {locked && (
          <span
            className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-600"
            title="Locked from an earlier upload in this cycle. Fix it on the user's history page if it's wrong."
          >
            🔒 locked this cycle
          </span>
        )}
      </dd>
    </div>
  );
}

function formatResetDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}
