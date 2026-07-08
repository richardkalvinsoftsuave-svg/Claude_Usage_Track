import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getUserHistory } from '../api';
import type { UserHistoryResponse } from '../types';

export default function UserDetailPage() {
  const { name } = useParams<{ name: string }>();
  const [data, setData] = useState<UserHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!name) return;
    setLoading(true);
    setError(null);
    getUserHistory(decodeURIComponent(name)).then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [name]);

  useEffect(() => {
    if (!data?.trend.length || !canvasRef.current) return;
    const labels = data.trend.map((p) => p.uploaded_at.slice(0, 10));
    const sessionData = data.trend.map((p) => p.session_usage_pct);
    const weeklyData = data.trend.map((p) => p.weekly_usage_pct);
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
            { label: 'Session %', data: sessionData, borderColor: '#3b82f6', backgroundColor: '#3b82f620', fill: false, tension: 0.3 },
            { label: 'Weekly %', data: weeklyData, borderColor: '#ef4444', backgroundColor: '#ef444420', fill: false, tension: 0.3 },
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

  if (loading) return <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>;
  if (error) return <div className="rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-700">{error}</div>;
  if (!data) return null;

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3">
        <Link to="/dashboard" className="text-sm text-blue-600 hover:underline">← Dashboard</Link>
        <h1 className="text-2xl font-bold text-gray-900">{data.uploader_name}</h1>
        <span className="text-sm text-gray-500">{data.total_uploads} uploads</span>
      </div>

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
                <th className="px-4 py-2 font-medium text-gray-500 text-right">Session</th>
                <th className="px-4 py-2 font-medium text-gray-500 text-right">Weekly</th>
                <th className="px-4 py-2 font-medium text-gray-500 text-right">Fable</th>
              </tr>
            </thead>
            <tbody>
              {data.uploads.map((u) => (
                <tr key={u.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-500 whitespace-nowrap">{new Date(u.uploaded_at).toLocaleString()}</td>
                  <td className="px-4 py-2">{u.plan_tier || '—'}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{u.session_usage_pct != null ? `${u.session_usage_pct}%` : '—'}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{u.weekly_usage_pct != null ? `${u.weekly_usage_pct}%` : '—'}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{u.weekly_fable_usage_pct != null ? `${u.weekly_fable_usage_pct}%` : '—'}</td>
                </tr>
              ))}
              {data.uploads.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No uploads yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
