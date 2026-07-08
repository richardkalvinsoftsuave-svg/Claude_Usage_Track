import { useState, useRef, useEffect } from 'react';
import { uploadImage, confirmUpload, reextract, getManagers, getTeams, getTeamMembers } from '../api';
import type { UploadPreviewResponse, Manager, Team, TeamMember } from '../types';

const EXTRACTION_METHOD = 'ocr';

export default function UploadPage() {
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<UploadPreviewResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploaderName, setUploaderName] = useState('');
  const [extracted, setExtracted] = useState<Record<string, string | number | null>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  // Org hierarchy state
  const [managers, setManagers] = useState<Manager[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [selectedManagerId, setSelectedManagerId] = useState<number | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);

  // Fetch managers on mount
  useEffect(() => {
    getManagers()
      .then(setManagers)
      .catch(() => setManagers([]));
  }, []);

  // Fetch teams when manager changes
  useEffect(() => {
    if (selectedManagerId != null) {
      getTeams(selectedManagerId)
        .then((t) => {
          setTeams(t);
          if (selectedTeamId != null && !t.find((x) => x.id === selectedTeamId)) {
            setSelectedTeamId(null);
          }
        })
        .catch(() => setTeams([]));
    } else {
      setTeams([]);
      setSelectedTeamId(null);
    }
  }, [selectedManagerId]);

  // Fetch members when team changes
  useEffect(() => {
    if (selectedTeamId != null) {
      getTeamMembers(selectedTeamId)
        .then((m) => {
          setMembers(m);
          if (selectedMemberId != null && !m.find((x) => x.id === selectedMemberId)) {
            setSelectedMemberId(null);
            setUploaderName('');
          }
        })
        .catch(() => setMembers([]));
    } else {
      setMembers([]);
      setSelectedMemberId(null);
      setUploaderName('');
    }
  }, [selectedTeamId]);

  // Auto-fill uploader name when member is selected
  const handleMemberChange = (memberId: number | null) => {
    setSelectedMemberId(memberId);
    if (memberId != null) {
      const member = members.find((m) => m.id === memberId);
      setUploaderName(member?.name ?? '');
    } else {
      setUploaderName('');
    }
  };

  function initExtracted(p: UploadPreviewResponse) {
    setExtracted({
      auth_method: p.extracted.auth_method ?? '',
      email: p.extracted.email ?? '',
      organization: p.extracted.organization ?? '',
      plan_tier: p.extracted.plan_tier ?? '',
      session_usage_pct: p.extracted.session_usage_pct,
      weekly_usage_pct: p.extracted.weekly_usage_pct,
      weekly_fable_usage_pct: p.extracted.weekly_fable_usage_pct,
      session_reset_at: p.extracted.session_reset_at ?? '',
      weekly_reset_at: p.extracted.weekly_reset_at ?? '',
      weekly_fable_reset_at: p.extracted.weekly_fable_reset_at ?? '',
    });
  }

  function wasEdited(p: UploadPreviewResponse): boolean {
    const e = p.extracted;
    return (
      extracted.auth_method !== (e.auth_method ?? '') ||
      extracted.email !== (e.email ?? '') ||
      extracted.organization !== (e.organization ?? '') ||
      extracted.plan_tier !== (e.plan_tier ?? '') ||
      extracted.session_usage_pct !== e.session_usage_pct ||
      extracted.weekly_usage_pct !== e.weekly_usage_pct ||
      extracted.weekly_fable_usage_pct !== e.weekly_fable_usage_pct ||
      extracted.session_reset_at !== (e.session_reset_at ?? '') ||
      extracted.weekly_reset_at !== (e.weekly_reset_at ?? '') ||
      extracted.weekly_fable_reset_at !== (e.weekly_fable_reset_at ?? '')
    );
  }

  function handleUpload(file: File) {
    if (!file) return;
    setUploading(true);
    setError(null);
    setPreview(null);
    setSaved(false);
    uploadImage(file)
      .then((p) => {
        setPreview(p);
        initExtracted(p);
      })
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
      .then((p) => {
        setPreview(p);
        initExtracted(p);
      })
      .catch((e) => setError(e.message))
      .finally(() => setUploading(false));
  }

  function handleConfirm() {
    if (!preview || !uploaderName.trim()) return;
    if (selectedManagerId == null || selectedTeamId == null || selectedMemberId == null) {
      setError('Please select Manager, Team, and Member before saving.');
      return;
    }
    setSaving(true);
    setError(null);
    confirmUpload({
      uploader_name: uploaderName.trim(),
      image_path: preview.image_path,
      original_filename: preview.original_filename,
      manager_id: selectedManagerId,
      team_id: selectedTeamId,
      auth_method: extracted.auth_method?.toString() || null,
      email: extracted.email?.toString() || null,
      organization: extracted.organization?.toString() || null,
      plan_tier: extracted.plan_tier?.toString() || null,
      session_usage_pct: extracted.session_usage_pct != null ? Number(extracted.session_usage_pct) : null,
      weekly_usage_pct: extracted.weekly_usage_pct != null ? Number(extracted.weekly_usage_pct) : null,
      weekly_fable_usage_pct: extracted.weekly_fable_usage_pct != null ? Number(extracted.weekly_fable_usage_pct) : null,
      session_reset_at: extracted.session_reset_at?.toString() || null,
      weekly_reset_at: extracted.weekly_reset_at?.toString() || null,
      weekly_fable_reset_at: extracted.weekly_fable_reset_at?.toString() || null,
      extraction_method: EXTRACTION_METHOD,
      raw_extracted_text: preview.raw_text,
      was_manually_edited: wasEdited(preview),
    })
      .then(() => setSaved(true))
      .catch((e) => setError(e.message))
      .finally(() => setSaving(false));
  }

  function handleReset() {
    setPreview(null);
    setSaved(false);
    setError(null);
    setUploaderName('');
    if (fileRef.current) fileRef.current.value = '';
  }

  const fieldProps = (key: string, type: string = 'text') => ({
    name: key,
    value: extracted[key] != null ? String(extracted[key]) : '',
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = type === 'number' ? (e.target.value === '' ? null : Number(e.target.value)) : e.target.value;
      setExtracted((prev) => ({ ...prev, [key]: val }));
    },
    className: 'mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500',
  });

  const canConfirm = uploaderName.trim() && selectedManagerId != null && selectedTeamId != null && selectedMemberId != null;

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

            <div className="flex-1 space-y-4">
              {/* ── Org hierarchy dropdowns (Manager → Team → Member) ── */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Manager *</label>
                  <select
                    value={selectedManagerId ?? ''}
                    onChange={(e) => setSelectedManagerId(e.target.value ? Number(e.target.value) : null)}
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  >
                    <option value="">-- Select --</option>
                    {managers.map((m) => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Team *</label>
                  <select
                    value={selectedTeamId ?? ''}
                    onChange={(e) => setSelectedTeamId(e.target.value ? Number(e.target.value) : null)}
                    disabled={selectedManagerId == null}
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-400"
                  >
                    <option value="">-- Select --</option>
                    {teams.map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Member (uploader) *</label>
                  <select
                    value={selectedMemberId ?? ''}
                    onChange={(e) => handleMemberChange(e.target.value ? Number(e.target.value) : null)}
                    disabled={selectedTeamId == null}
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-400"
                  >
                    <option value="">-- Select --</option>
                    {members.map((m) => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Uploader name</label>
                <input type="text" value={uploaderName} onChange={(e) => setUploaderName(e.target.value)} placeholder="Auto-filled from member selection" className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm bg-gray-50 text-gray-600 focus:border-blue-500 focus:ring-blue-500" readOnly />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {(['auth_method', 'email'] as const).map((k) => (
                  <div key={k}>
                    <label className="block text-sm font-medium text-gray-700 capitalize">{k.replace('_', ' ')}</label>
                    <input {...fieldProps(k, k === 'email' ? 'email' : 'text')} />
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {(['organization', 'plan_tier'] as const).map((k) => (
                  <div key={k}>
                    <label className="block text-sm font-medium text-gray-700 capitalize">{k.replace('_', ' ')}</label>
                    <input {...fieldProps(k)} />
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {(['session_usage_pct', 'weekly_usage_pct', 'weekly_fable_usage_pct'] as const).map((k) => (
                  <div key={k}>
                    <label className="block text-sm font-medium text-gray-700 capitalize">{k.replace(/_/g, ' ').replace('pct', '%')}</label>
                    <input {...fieldProps(k, 'number')} min={0} max={100} />
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {(['session_reset_at', 'weekly_reset_at', 'weekly_fable_reset_at'] as const).map((k) => (
                  <div key={k}>
                    <label className="block text-sm font-medium text-gray-700 capitalize">{k.replace(/_/g, ' ').replace('at', '(UTC)')}</label>
                    <input {...fieldProps(k)} type="datetime-local" />
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-3 pt-2">
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
          <p className="text-gray-600 mb-4">Your usage data has been recorded.</p>
          <button onClick={handleReset} className="inline-flex rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500">Upload another</button>
        </div>
      )}
    </div>
  );
}
