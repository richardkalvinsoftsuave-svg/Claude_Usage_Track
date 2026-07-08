import { useState, useEffect, useMemo } from 'react';
import { getDashboardSummary } from '../api';
import type { DashboardSummary } from '../types';
import { Link } from 'react-router-dom';

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getDashboardSummary(days).then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [days]);

  const trendData = useMemo(() => {
    if (!data?.per_user_trends) return null;
    const users = data.per_user_trends;
    const allDates = new Set<string>();
    const userMap: Record<string, Record<string, number | null>> = {};
    for (const u of users) {
      userMap[u.uploader_name] = {};
      for (const p of u.points) {
        const d = p.uploaded_at.slice(0, 10);
        allDates.add(d);
        userMap[u.uploader_name][d] = p.weekly_usage_pct ?? p.session_usage_pct;
      }
    }
    const labels = [...allDates].sort();
    const colors = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];
    const datasets = Object.entries(userMap).map(([name, map], i) => ({
      label: name,
      data: labels.map((d) => map[d] ?? null),
      borderColor: colors[i % colors.length],
      backgroundColor: colors[i % colors.length] + '20',
      fill: false,
      tension: 0.3,
    }));
    return { labels, datasets };
  }, [data]);

  const canvasRef = (e: HTMLCanvasElement | null) => {
    if (!e || !trendData || trendData.labels.length <= 1) return;
    import('chart.js/auto').then(({ Chart }) => {
      const existing = Chart.getChart(e);
      if (existing) existing.destroy();
      new Chart(e, {
        type: 'line',
        data: { labels: trendData.labels, datasets: trendData.datasets as any },
        options: {
          responsive: true,
          interaction: { intersect: false, mode: 'index' },
          plugins: { legend: { position: 'bottom' } },
          scales: { y: { min: 0, max: 100, title: { display: true, text: '%' } } },
        },
      });
    });
  };

  if (loading) return <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>;
  if (error) return <div className="rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-700">{error}</div>;
  if (!data) return null;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500">
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Uploads today" value={data.uploads_today} />
        <StatCard label="Uploads this week" value={data.uploads_this_week} />
        <StatCard label="Avg session %" value={data.team_avg_session_usage != null ? `${Math.round(data.team_avg_session_usage)}%` : '—'} />
        <StatCard label="Avg weekly %" value={data.team_avg_weekly_usage != null ? `${Math.round(data.team_avg_weekly_usage)}%` : '—'} />
      </div>

      {data.leaderboard.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Leaderboard</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-gray-200">
                  <th className="pb-2 font-medium text-gray-500">#</th>
                  <th className="pb-2 font-medium text-gray-500">User</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Session</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Weekly</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Last upload</th>
                </tr>
              </thead>
              <tbody>
                {data.leaderboard.map((entry, i) => (
                  <tr key={entry.uploader_name} className="border-b border-gray-100 last:border-0">
                    <td className="py-2 font-mono text-gray-400">{i + 1}</td>
                    <td className="py-2">
                      <Link to={`/dashboard/user/${encodeURIComponent(entry.uploader_name)}`} className="text-blue-600 hover:underline font-medium">{entry.uploader_name}</Link>
                    </td>
                    <td className="py-2 text-right tabular-nums">{entry.latest_session_pct != null ? `${entry.latest_session_pct}%` : '—'}</td>
                    <td className="py-2 text-right tabular-nums">{entry.latest_weekly_pct != null ? `${entry.latest_weekly_pct}%` : '—'}</td>
                    <td className="py-2 text-right text-gray-500 text-xs">{entry.last_upload_at ? new Date(entry.last_upload_at).toLocaleDateString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {trendData && trendData.labels.length > 1 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Usage trends</h2>
          <canvas ref={canvasRef} />
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <p className="text-xs font-medium text-gray-500 uppercase">{label}</p>
      <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}
