import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { getDashboardSummary, getDashboardCompare } from '../api';
import type { DashboardSummary, DashboardCompareResponse, DailyUsage } from '../types';
import { Link } from 'react-router-dom';

type SortMode = { date: string; metric: 'weekly' | 'fable' } | null;

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [sort, setSort] = useState<SortMode>(null);
  const [trendMetric, setTrendMetric] = useState<'weekly' | 'fable'>('weekly');

  // Comparison state
  const [compareFrom, setCompareFrom] = useState('');
  const [compareTo, setCompareTo] = useState('');
  const [compareData, setCompareData] = useState<DashboardCompareResponse | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  // Image modal state
  const [modalImage, setModalImage] = useState<string | null>(null);

  // Fetch dashboard data
  useEffect(() => {
    setLoading(true);
    setError(null);
    getDashboardSummary({ days })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [days]);

  // Default comparison dates: yesterday & today
  useEffect(() => {
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    setCompareTo(today.toISOString().slice(0, 10));
    setCompareFrom(yesterday.toISOString().slice(0, 10));
  }, []);

  const handleCompare = useCallback(async () => {
    if (!compareFrom || !compareTo) return;
    setCompareLoading(true);
    setCompareError(null);
    try {
      const result = await getDashboardCompare({ from: compareFrom, to: compareTo });
      setCompareData(result);
    } catch (e: any) {
      setCompareError(e.message);
    } finally {
      setCompareLoading(false);
    }
  }, [compareFrom, compareTo]);

  // Trend chart data — one metric at a time so lines never jump between
  // weekly and Fable usage (they're different limits, not one series).
  const trendData = useMemo(() => {
    if (!data?.per_user_trends) return null;
    const users = data.per_user_trends;
    const allDates = new Set<string>();
    const userMap: Record<string, Record<string, number | null>> = {};
    for (const u of users) {
      userMap[u.email] = {};
      for (const p of u.points) {
        const d = p.uploaded_at.slice(0, 10);
        allDates.add(d);
        userMap[u.email][d] = trendMetric === 'weekly' ? p.weekly_usage_pct : p.weekly_fable_usage_pct;
      }
    }
    const labels = [...allDates].sort();
    const colors = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];
    const datasets = Object.entries(userMap).map(([email, map], i) => ({
      label: email,
      data: labels.map((d) => map[d] ?? null),
      borderColor: colors[i % colors.length],
      backgroundColor: colors[i % colors.length] + '20',
      fill: false,
      tension: 0.3,
    }));
    return { labels, datasets };
  }, [data, trendMetric]);

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

  const sortedUsers = useMemo(() => {
    if (!data) return [];
    if (!sort) return data.users;
    const metric = sort.metric;
    return [...data.users].sort((a, b) => {
      const aVal = a.daily[sort.date]?.[metric] ?? -1;
      const bVal = b.daily[sort.date]?.[metric] ?? -1;
      return bVal - aVal;
    });
  }, [data, sort]);

  const formatDateHeader = (d: string) => {
    const date = new Date(d);
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  const renderCell = (day: DailyUsage | undefined) => {
    if (!day) return <span className="text-gray-300">—</span>;
    const risk = day.weekly == null ? '' : day.weekly >= 85 ? 'bg-red-50 text-red-700' : day.weekly >= 50 ? 'bg-amber-50 text-amber-700' : '';
    return (
      <div className={`leading-tight rounded px-1 py-0.5 ${risk}`}>
        <div className="font-medium">{day.weekly != null ? `${day.weekly}%` : '—'}</div>
        <div className="text-[10px] text-gray-400">{day.fable != null ? `F ${day.fable}%` : ''}</div>
      </div>
    );
  };

  if (loading) return <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>;
  if (error) return <div className="rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-700">{error}</div>;
  if (!data) return null;

  // Newest date first so today's column sits right next to the sticky user
  // column in the day-wise grid and is visible without scrolling right.
  const displayDates = [...data.dates].reverse();

  return (
    <div className="space-y-8">
      {/* ── Header with filters ── */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex items-center gap-2">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500">
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <InfoPopover title="Date range">
            <p><strong>What it's for:</strong> controls how far back the Day-wise usage grid and Usage trends chart look.</p>
            <p><strong>What it doesn't affect:</strong> the Leaderboard (always shows each user's latest upload) and Compare dates (uses its own From/To pickers).</p>
          </InfoPopover>
        </div>
      </div>

      {/* ── Stat cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Uploads today" value={data.uploads_today} />
        <StatCard label="Uploads this week" value={data.uploads_this_week} />
        <StatCard label="Active users" value={data.users.length} />
        <StatCard label="Leader #1" value={data.leaderboard[0]?.email ?? '—'} small />
      </div>

      {/* ── Date comparison ── */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center gap-2 mb-4">
          <h2 className="text-lg font-semibold">Compare dates</h2>
          <InfoPopover title="Compare dates">
            <p><strong>What it's for:</strong> see how much a user's usage changed between any two dates.</p>
            <p><strong>How to use:</strong> pick a From and To date, then click Compare.</p>
            <p><strong>Δ (delta):</strong> the change between the two dates. It shows "↻ reset" instead of a number when the weekly cycle reset in between — a raw difference would be misleading there, since the % dropped because a new week started, not because usage went down.</p>
          </InfoPopover>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">From</label>
            <input
              type="date"
              value={compareFrom}
              onChange={(e) => setCompareFrom(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">To</label>
            <input
              type="date"
              value={compareTo}
              onChange={(e) => setCompareTo(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
            />
          </div>
          <button
            onClick={handleCompare}
            disabled={compareLoading || !compareFrom || !compareTo}
            className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 disabled:opacity-50"
          >
            {compareLoading ? '…' : 'Compare'}
          </button>
        </div>
        {compareError && <p className="mt-3 text-sm text-red-600">{compareError}</p>}
        {compareData && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-gray-200">
                  <th className="pb-2 font-medium text-gray-500">User</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Weekly {compareData.from_date}</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Weekly {compareData.to_date}</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Δ</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Fable {compareData.from_date}</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Fable {compareData.to_date}</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Δ</th>
                </tr>
              </thead>
              <tbody>
                {compareData.users.map((u) => (
                  <tr key={u.email} className="border-b border-gray-100 last:border-0">
                    <td className="py-2 font-medium text-blue-600">
                      <Link to={`/dashboard/user/${encodeURIComponent(u.email)}`} className="hover:underline">{u.email}</Link>
                    </td>
                    <td className="py-2 text-right tabular-nums">{u.weekly_from != null ? `${u.weekly_from}%` : '—'}</td>
                    <td className="py-2 text-right tabular-nums">{u.weekly_to != null ? `${u.weekly_to}%` : '—'}</td>
                    <DeltaCell value={u.weekly_delta} resetOccurred={u.weekly_reset_occurred} />
                    <td className="py-2 text-right tabular-nums">{u.fable_from != null ? `${u.fable_from}%` : '—'}</td>
                    <td className="py-2 text-right tabular-nums">{u.fable_to != null ? `${u.fable_to}%` : '—'}</td>
                    <DeltaCell value={u.fable_delta} resetOccurred={u.fable_reset_occurred} />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Leaderboard ── */}
      {data.leaderboard.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-lg font-semibold">Leaderboard</h2>
            <InfoPopover title="Leaderboard">
              <p><strong>What it's for:</strong> each user's most recent usage snapshot, with anyone at risk of hitting their cap surfaced to the top.</p>
              <p><strong>Weekly / Fable:</strong> the % recorded in that user's latest upload. The small "→ X% by reset" line is a projection of where they're headed by the time their cycle resets, based on their recent pace.</p>
              <p><strong>Risk:</strong> shows "At risk" when a user is projected to hit 100% before their cycle resets at the current pace — a heads-up to check in with them or slow down.</p>
              <p><strong>Image:</strong> view the screenshot behind that user's latest numbers.</p>
            </InfoPopover>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-gray-200">
                  <th className="pb-2 font-medium text-gray-500">#</th>
                  <th className="pb-2 font-medium text-gray-500">User</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Weekly</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Fable</th>
                  <th className="pb-2 font-medium text-gray-500 text-center">Risk</th>
                  <th className="pb-2 font-medium text-gray-500 text-right">Last upload</th>
                  <th className="pb-2 font-medium text-gray-500 text-center">Image</th>
                </tr>
              </thead>
              <tbody>
                {data.leaderboard.map((entry, i) => (
                  <tr key={entry.email} className="border-b border-gray-100 last:border-0">
                    <td className="py-2 font-mono text-gray-400">{i + 1}</td>
                    <td className="py-2">
                      <Link to={`/dashboard/user/${encodeURIComponent(entry.email)}`} className="text-blue-600 hover:underline font-medium">{entry.email}</Link>
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      {entry.latest_weekly != null ? `${entry.latest_weekly}%` : '—'}
                      {entry.weekly_projected_pct != null && (
                        <div className="text-[10px] text-gray-400">→ {entry.weekly_projected_pct}% by reset</div>
                      )}
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      {entry.latest_fable != null ? `${entry.latest_fable}%` : '—'}
                      {entry.fable_projected_pct != null && (
                        <div className="text-[10px] text-gray-400">→ {entry.fable_projected_pct}% by reset</div>
                      )}
                    </td>
                    <td className="py-2 text-center">
                      {(entry.weekly_at_risk || entry.fable_at_risk) ? (
                        <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium text-red-700" title="Projected to hit 100% before the cycle resets at current pace">
                          At risk
                        </span>
                      ) : (
                        <span className="text-xs text-gray-300">—</span>
                      )}
                    </td>
                    <td className="py-2 text-right text-gray-500 text-xs">{entry.last_upload_at ? new Date(entry.last_upload_at).toLocaleDateString() : '—'}</td>
                    <td className="py-2 text-center">
                      {entry.latest_image_path ? (
                        <button
                          onClick={() => setModalImage(entry.latest_image_path ?? null)}
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

      {/* ── Day-wise grid ── */}
      {data.dates.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold">Day-wise usage</h2>
              <InfoPopover title="Day-wise usage">
                <p><strong>What it's for:</strong> a day-by-day usage grid across all users for the selected date range, with today shown first so you don't have to scroll to find it.</p>
                <p><strong>How to use:</strong> change the range with the selector at the top of the page, or click "W" / "F" under any date to sort everyone by that day's Weekly / Fable %.</p>
                <p><strong>Cells:</strong> the top number is Weekly %, the small "F" number is Fable %, using the highest reading recorded that day if there were multiple uploads. Amber = 50%+, red = 85%+ usage, as a quick visual warning.</p>
              </InfoPopover>
            </div>
            {sort && (
              <button
                onClick={() => setSort(null)}
                className="text-xs text-blue-600 hover:underline"
              >
                Clear sort
              </button>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-max">
              <thead>
                <tr className="text-left border-b border-gray-200">
                  <th className="pb-2 pr-4 font-medium text-gray-500 sticky left-0 bg-white min-w-[200px]">User</th>
                  {displayDates.map((d) => (
                    <th key={d} className="pb-2 px-2 font-medium text-gray-500 text-center min-w-[80px]">
                      <div>{formatDateHeader(d)}</div>
                      <div className="flex justify-center gap-1 mt-1">
                        <button
                          onClick={() => setSort({ date: d, metric: 'weekly' })}
                          className={`text-[10px] px-1 rounded ${sort?.date === d && sort.metric === 'weekly' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                          title="Sort by weekly"
                        >
                          W
                        </button>
                        <button
                          onClick={() => setSort({ date: d, metric: 'fable' })}
                          className={`text-[10px] px-1 rounded ${sort?.date === d && sort.metric === 'fable' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                          title="Sort by fable"
                        >
                          F
                        </button>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedUsers.map((user) => (
                  <tr key={user.email} className="border-b border-gray-100 last:border-0">
                    <td className="py-2 pr-4 sticky left-0 bg-white">
                      <Link to={`/dashboard/user/${encodeURIComponent(user.email)}`} className="text-blue-600 hover:underline font-medium block truncate max-w-[200px]">{user.email}</Link>
                      <span className="text-[10px] text-gray-400">{user.plan_tier || '—'}</span>
                    </td>
                    {displayDates.map((d) => (
                      <td key={d} className="py-2 px-2 text-center tabular-nums">
                        {renderCell(user.daily[d])}
                      </td>
                    ))}
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
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Usage trends</h2>
            <div className="flex gap-1">
              <button
                onClick={() => setTrendMetric('weekly')}
                className={`text-xs px-2 py-1 rounded ${trendMetric === 'weekly' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              >
                Weekly
              </button>
              <button
                onClick={() => setTrendMetric('fable')}
                className={`text-xs px-2 py-1 rounded ${trendMetric === 'fable' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              >
                Fable
              </button>
            </div>
          </div>
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

function InfoPopover({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={`About ${title}`}
        className="w-5 h-5 inline-flex items-center justify-center rounded-full bg-gray-100 text-gray-500 hover:bg-gray-200 text-xs font-bold leading-none"
      >
        !
      </button>
      {open && (
        <div className="absolute z-20 top-full left-0 mt-2 w-80 rounded-lg border border-gray-200 bg-white p-4 shadow-xl text-sm text-gray-700 space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">{title}</h3>
            <button type="button" onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600 text-lg leading-none">×</button>
          </div>
          {children}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, small }: { label: string; value: string | number; small?: boolean }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <p className="text-xs font-medium text-gray-500 uppercase">{label}</p>
      <p
        className={`mt-1 font-bold text-gray-900 truncate ${small ? 'text-base' : 'text-2xl'}`}
        title={typeof value === 'string' ? value : undefined}
      >
        {value}
      </p>
    </div>
  );
}

function DeltaCell({ value, resetOccurred }: { value: number | null; resetOccurred?: boolean }) {
  if (resetOccurred) {
    return (
      <td
        className="py-2 text-right tabular-nums font-medium text-blue-600"
        title="A reset happened between these two dates, so a raw delta would be misleading."
      >
        ↻ reset
      </td>
    );
  }
  if (value == null) return <td className="py-2 text-right tabular-nums text-gray-400">—</td>;
  const color = value > 0 ? 'text-red-600' : value < 0 ? 'text-green-600' : 'text-gray-600';
  const sign = value > 0 ? '+' : '';
  return <td className={`py-2 text-right tabular-nums font-medium ${color}`}>{sign}{value}%</td>;
}
