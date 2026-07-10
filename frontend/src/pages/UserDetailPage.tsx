import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getUserHistory, updateResetDate } from '../api';
import type { UserHistoryResponse } from '../types';

type EditableMetric = 'weekly' | 'fable';

function toDatetimeLocal(iso: string | null | undefined): string {
  if (!iso) return '';
  return iso.slice(0, 16);
}

function fromDatetimeLocal(value: string): string {
  // Reset dates are stored/displayed as UTC wall-clock everywhere else in
  // this app, so treat the picked value the same way rather than applying
  // the browser's local timezone offset.
  return `${value}:00Z`;
}

export default function UserDetailPage() {
  const { email } = useParams<{ email: string }>();
  const [data, setData] = useState<UserHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [editingMetric, setEditingMetric] = useState<EditableMetric | null>(null);
  const [editValue, setEditValue] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const [modalImage, setModalImage] = useState<string | null>(null);

  const loadHistory = useCallback(() => {
    if (!email) return Promise.resolve();
    setError(null);
    return getUserHistory(decodeURIComponent(email))
      .then(setData)
      .catch((e) => setError(e.message));
  }, [email]);

  useEffect(() => {
    setLoading(true);
    loadHistory().finally(() => setLoading(false));
  }, [loadHistory]);

  useEffect(() => {
    if (!data?.trend.length || !canvasRef.current) return;
    const labels = data.trend.map((p) => p.uploaded_at.slice(0, 10));
    const weeklyData = data.trend.map((p) => p.weekly_usage_pct);
    const fableData = data.trend.map((p) => p.weekly_fable_usage_pct);
    import('chart.js/auto').then(({ Chart }) => {
      const e = canvasRef.current;
      if (!e) return;
      const existing = Chart.getChart(e);
      if (existing) existing.destroy();
      new Chart(e, {
        type: 'line',
        data: {
          labels,
          datasets: [
            { label: 'Weekly %', data: weeklyData, borderColor: '#ef4444', backgroundColor: '#ef444420', fill: false, tension: 0.3 },
            { label: 'Fable %', data: fableData, borderColor: '#f59e0b', backgroundColor: '#f59e0b20', fill: false, tension: 0.3 },
          ],
        },
        options: {
          responsive: true,
          interaction: { intersect: false, mode: 'index' },
          plugins: { legend: { position: 'bottom' } },
          scales: { y: { min: 0, max: 100, title: { display: true, text: '%' } } },
        },
      });
    });
  }, [data]);

  function startEdit(metric: EditableMetric, currentValue: string | null | undefined) {
    setEditingMetric(metric);
    setEditValue(toDatetimeLocal(currentValue));
    setEditError(null);
  }

  async function handleSaveReset() {
    if (!email || !editingMetric || !editValue) return;
    setEditSaving(true);
    setEditError(null);
    try {
      await updateResetDate(decodeURIComponent(email), {
        metric: editingMetric,
        reset_at: fromDatetimeLocal(editValue),
      });
      setEditingMetric(null);
      await loadHistory();
    } catch (e: any) {
      setEditError(e.message);
    } finally {
      setEditSaving(false);
    }
  }

  if (loading) return <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>;
  if (error) return <div className="rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-700">{error}</div>;
  if (!data) return null;

  const latest = data.uploads[0];

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3 flex-wrap">
        <Link to="/dashboard" className="text-sm text-blue-600 hover:underline">← Dashboard</Link>
        <h1 className="text-2xl font-bold text-gray-900">{data.email}</h1>
        <span className="text-sm text-gray-500">{data.total_uploads} uploads</span>
      </div>

      {latest && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-1">Cycle reset dates</h2>
          <p className="text-xs text-gray-400 mb-4">
            These are locked in place after the first upload of a cycle so day-to-day comparisons stay consistent.
            Only correct them here if the extracted value was wrong.
          </p>
          <div className="space-y-3">
            <ResetDateRow
              label="Weekly reset"
              value={latest.weekly_reset_at}
              editing={editingMetric === 'weekly'}
              editValue={editValue}
              saving={editSaving}
              onEdit={() => startEdit('weekly', latest.weekly_reset_at)}
              onChange={setEditValue}
              onCancel={() => setEditingMetric(null)}
              onSave={handleSaveReset}
            />
            <ResetDateRow
              label="Fable reset"
              value={latest.weekly_fable_reset_at}
              editing={editingMetric === 'fable'}
              editValue={editValue}
              saving={editSaving}
              onEdit={() => startEdit('fable', latest.weekly_fable_reset_at)}
              onChange={setEditValue}
              onCancel={() => setEditingMetric(null)}
              onSave={handleSaveReset}
            />
          </div>
          {editError && <p className="mt-3 text-sm text-red-600">{editError}</p>}
        </div>
      )}

      {data.trend.length > 1 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Usage over time</h2>
          <canvas ref={canvasRef} />
        </div>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="p-4 border-b border-gray-200"><h2 className="text-lg font-semibold">Upload history</h2></div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b border-gray-200">
                <th className="px-4 py-2 font-medium text-gray-500">Date</th>
                <th className="px-4 py-2 font-medium text-gray-500">Plan</th>
                <th className="px-4 py-2 font-medium text-gray-500 text-right">Weekly</th>
                <th className="px-4 py-2 font-medium text-gray-500 text-right">Fable</th>
                <th className="px-4 py-2 font-medium text-gray-500 text-center">Image</th>
              </tr>
            </thead>
            <tbody>
              {data.uploads.map((u) => (
                <tr key={u.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-500 whitespace-nowrap">{new Date(u.uploaded_at).toLocaleString()}</td>
                  <td className="px-4 py-2">{u.plan_tier || '—'}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{u.weekly_usage_pct != null ? `${u.weekly_usage_pct}%` : '—'}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{u.weekly_fable_usage_pct != null ? `${u.weekly_fable_usage_pct}%` : '—'}</td>
                  <td className="px-4 py-2 text-center">
                    {u.image_path ? (
                      <button
                        onClick={() => setModalImage(u.image_path)}
                        className="px-2 py-1 text-xs rounded bg-blue-50 text-blue-600 hover:bg-blue-100"
                      >
                        View
                      </button>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
              {data.uploads.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No uploads yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {modalImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setModalImage(null)}
        >
          <div className="relative max-w-3xl max-h-[90vh] p-2" onClick={(e) => e.stopPropagation()}>
            <button
              className="absolute top-4 right-4 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-white/80 text-gray-700 hover:bg-white text-lg font-bold"
              onClick={() => setModalImage(null)}
            >
              ×
            </button>
            <img src={`/uploads/${modalImage}`} alt="Uploaded screenshot" className="max-w-full max-h-[85vh] rounded-lg shadow-xl" />
          </div>
        </div>
      )}
    </div>
  );
}

function ResetDateRow({
  label,
  value,
  editing,
  editValue,
  saving,
  onEdit,
  onChange,
  onCancel,
  onSave,
}: {
  label: string;
  value: string | null;
  editing: boolean;
  editValue: string;
  saving: boolean;
  onEdit: () => void;
  onChange: (v: string) => void;
  onCancel: () => void;
  onSave: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="w-32 shrink-0 text-sm font-medium text-gray-500">{label}</span>
      {editing ? (
        <>
          <input
            type="datetime-local"
            value={editValue}
            onChange={(e) => onChange(e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
          />
          <span className="text-xs text-gray-400">UTC</span>
          <button
            onClick={onSave}
            disabled={saving || !editValue}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-500 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
          <button onClick={onCancel} className="text-xs text-gray-500 hover:text-gray-700">Cancel</button>
        </>
      ) : (
        <>
          <span className="text-sm text-gray-900">{value ? new Date(value).toLocaleString() : '—'}</span>
          <button onClick={onEdit} className="text-xs text-blue-600 hover:underline">Edit</button>
        </>
      )}
    </div>
  );
}
