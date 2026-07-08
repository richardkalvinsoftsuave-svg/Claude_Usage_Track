import { useState, useEffect, useMemo, useCallback } from 'react';
import { getDashboardSummary, getManagers, getTeams, resetTeamUsage } from '../api';
import type { DashboardSummary, Manager, Team } from '../types';
import { Link } from 'react-router-dom';

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  // Org filter state
  const [managers, setManagers] = useState<Manager[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [managerFilter, setManagerFilter] = useState<number | null>(null);
  const [teamFilter, setTeamFilter] = useState<number | null>(null);

  // Fetch managers on mount
  useEffect(() => {
    getManagers()
      .then(setManagers)
      .catch(() => setManagers([]));
  }, []);

  // Fetch teams when manager filter changes
  useEffect(() => {
    if (managerFilter != null) {
      getTeams(managerFilter)
        .then((t) => {
          setTeams(t);
          if (teamFilter != null && !t.find((x) => x.id === teamFilter)) {
            setTeamFilter(null);
          }
        })
        .catch(() => setTeams([]));
    } else {
      getTeams()
        .then(setTeams)
        .catch(() => setTeams([]));
    }
  }, [managerFilter]);

  // Image modal state
  const [modalImage, setModalImage] = useState<string | null>(null);

  // Reset state
  const [resettingTeamId, setResettingTeamId] = useState<number | null>(null);

  const handleResetTeam = async (teamId: number, teamName: string) => {
    if (!confirm(`Reset all usage data for team "${teamName}" to zero?`)) return;
    setResettingTeamId(teamId);
    try {
      await resetTeamUsage(teamId);
      // Refresh dashboard data
      const fresh = await getDashboardSummary({
        days,
        manager_id: managerFilter ?? undefined,
        team_id: teamFilter ?? undefined,
      });
      setData(fresh);
    } catch (e: any) {
      alert('Reset failed: ' + (e.message || 'Unknown error'));
    } finally {
      setResettingTeamId(null);
    }
  };

  // Fetch dashboard data
  useEffect(() => {
    setLoading(true);
    setError(null);
    getDashboardSummary({
      days,
      manager_id: managerFilter ?? undefined,
      team_id: teamFilter ?? undefined,
    })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [days, managerFilter, teamFilter]);

  // Trend chart data
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

  const canvasRef = useCallback((e: HTMLCanvasElement | null) => {
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
  }, [trendData]);

  if (loading) return <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>;
  if (error) return <div className="rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-700">{error}</div>;
  if (!data) return null;

  return (
    <div className="space-y-8">
      {/* ── Header with filters ── */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex flex-wrap items-center gap-3">
          {/* Manager filter */}
          <select
            value={managerFilter ?? ''}
            onChange={(e) => setManagerFilter(e.target.value ? Number(e.target.value) : null)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="">All Managers</option>
            {managers.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>

          {/* Team filter */}
          <select
            value={teamFilter ?? ''}
            onChange={(e) => setTeamFilter(e.target.value ? Number(e.target.value) : null)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="">All Teams</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>

          {/* Time range */}
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500">
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>

      {/* ── Stat cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Uploads today" value={data.uploads_today} />
        <StatCard label="Uploads this week" value={data.uploads_this_week} />
        <StatCard label="Avg session %" value={data.team_avg_session_usage != null ? `${Math.round(data.team_avg_session_usage)}%` : '—'} />
        <StatCard label="Avg weekly %" value={data.team_avg_weekly_usage != null ? `${Math.round(data.team_avg_weekly_usage)}%` : '—'} />
      </div>

      {/* ── Manager-wise summary cards ── */}
      {data.by_manager.length > 0 && (managerFilter == null || teamFilter == null) && (
        <div>
          <h2 className="text-lg font-semibold mb-4">By Manager</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {data.by_manager.map((m) => (
              <div
                key={m.manager_id}
                className="bg-white rounded-lg shadow p-4 cursor-pointer hover:shadow-md transition-shadow border border-transparent hover:border-blue-300"
                onClick={() => setManagerFilter(m.manager_id)}
              >
                <p className="text-sm font-semibold text-gray-800">{m.manager_name}</p>
                <p className="text-xs text-gray-500 mt-1">{m.team_count} team{m.team_count !== 1 ? 's' : ''}</p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-[10px] uppercase text-gray-400">Avg Session</p>
                    <p className="text-lg font-bold text-gray-900">{m.avg_session_pct != null ? `${Math.round(m.avg_session_pct)}%` : '—'}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase text-gray-400">Avg Weekly</p>
                    <p className="text-lg font-bold text-gray-900">{m.avg_weekly_pct != null ? `${Math.round(m.avg_weekly_pct)}%` : '—'}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Team-wise breakdown table ── */}
      {data.by_team.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">By Team</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-gray-200">
                  <th className="pb-2 font-medium text-gray-500">Team</th>
                  <th className="pb-2 font-medium text-gray-500">Manager</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Members</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Avg Session</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Avg Weekly</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Max Session</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Max Weekly</th>
                  <th className="pb-2 font-medium text-gray-500 text-center">Reset</th>
                </tr>
              </thead>
              <tbody>
                {data.by_team.map((t) => (
                  <tr
                    key={t.team_id}
                    className="border-b border-gray-100 last:border-0 cursor-pointer hover:bg-blue-50 transition-colors"
                    onClick={() => { setManagerFilter(null); setTeamFilter(t.team_id); }}
                  >
                    <td className="py-2 font-medium text-blue-600">{t.team_name}</td>
                    <td className="py-2 text-gray-500">{t.manager_name}</td>
                    <td className="py-2 text-right tabular-nums">{t.member_count}</td>
                    <td className="py-2 text-right tabular-nums font-mono">{t.avg_session_pct != null ? `${Math.round(t.avg_session_pct)}%` : '—'}</td>
                    <td className="py-2 text-right tabular-nums font-mono">{t.avg_weekly_pct != null ? `${Math.round(t.avg_weekly_pct)}%` : '—'}</td>
                    <td className="py-2 text-right tabular-nums font-mono text-orange-600">{t.max_session_pct != null ? `${t.max_session_pct}%` : '—'}</td>
                    <td className="py-2 text-right tabular-nums font-mono text-orange-600">{t.max_weekly_pct != null ? `${t.max_weekly_pct}%` : '—'}</td>
                    <td className="py-2 text-center" onClick={(e) => e.stopPropagation()}>
                      <button
                        disabled={resettingTeamId === t.team_id}
                        onClick={() => handleResetTeam(t.team_id, t.team_name)}
                        className="px-2 py-1 text-xs rounded bg-red-50 text-red-600 hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {resettingTeamId === t.team_id ? '…' : 'Reset'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Leaderboard ── */}
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
                  <th className="pb-2 font-medium text-gray-500 text-center">Image</th>
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
                    <td className="py-2 text-center">
                      {entry.latest_image_path ? (
                        <button
                          onClick={() => setModalImage(entry.latest_image_path)}
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
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Trend chart ── */}
      {trendData && trendData.labels.length > 1 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Usage trends</h2>
          <canvas ref={canvasRef} />
        </div>
      )}

      {/* ── Image modal ── */}
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
            <img src={modalImage} alt="Uploaded screenshot" className="max-w-full max-h-[85vh] rounded-lg shadow-xl" />
          </div>
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
