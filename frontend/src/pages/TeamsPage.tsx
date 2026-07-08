import { useState, useEffect, useCallback } from 'react';
import {
  getManagers, createManager, updateManager, deleteManager,
  getTeams, createTeam, updateTeam, deleteTeam,
  getTeamMembers, createTeamMember, updateTeamMember, deleteTeamMember,
} from '../api';
import type { Manager, Team, TeamMember } from '../types';

export default function TeamsPage() {
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Teams</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <ManagersSection />
        <TeamsSection />
        <MembersSection />
      </div>
    </div>
  );
}

// ── Inline editable row ──────────────────────────────────────────

function InlineRow({
  value,
  onSave,
  onDelete,
  placeholder,
}: {
  value: string;
  onSave: (v: string) => Promise<void>;
  onDelete: () => Promise<void>;
  placeholder?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    const trimmed = text.trim();
    if (!trimmed || trimmed === value) { setEditing(false); setText(value); return; }
    setSaving(true);
    try { await onSave(trimmed); setEditing(false); } catch { /* keep editing */ }
    finally { setSaving(false); }
  };

  if (editing) {
    return (
      <form onSubmit={(e) => { e.preventDefault(); handleSave(); }} className="flex gap-1">
        <input
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={placeholder}
          className="flex-1 rounded border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:ring-blue-500"
        />
        <button type="submit" disabled={saving} className="text-green-600 hover:text-green-800 text-sm px-1" title="Save">✓</button>
        <button type="button" onClick={() => { setText(value); setEditing(false); }} className="text-gray-400 hover:text-gray-600 text-sm px-1" title="Cancel">✕</button>
      </form>
    );
  }

  return (
    <div className="flex items-center gap-2 group">
      <span className="flex-1 text-sm text-gray-800">{value}</span>
      <button onClick={() => setEditing(true)} className="text-gray-400 hover:text-blue-600 text-xs opacity-0 group-hover:opacity-100 transition-opacity" title="Edit">✎</button>
      <button onClick={onDelete} className="text-gray-400 hover:text-red-600 text-xs opacity-0 group-hover:opacity-100 transition-opacity" title="Delete">✕</button>
    </div>
  );
}

// ── Managers Section ─────────────────────────────────────────────

function ManagersSection() {
  const [items, setItems] = useState<Manager[]>([]);
  const [newName, setNewName] = useState('');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getManagers().then(setItems).catch(() => setItems([]));
  }, []);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    const name = newName.trim();
    if (!name) return;
    setError(null);
    try {
      await createManager(name);
      setNewName('');
      load();
    } catch (e: any) { setError(e.message); }
  };

  return (
    <div className="bg-white rounded-lg shadow p-5">
      <h2 className="text-base font-semibold text-gray-800 mb-3">Managers</h2>

      <form onSubmit={(e) => { e.preventDefault(); add(); }} className="flex gap-2 mb-3">
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="New manager name"
          className="flex-1 rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:ring-blue-500"
        />
        <button type="submit" disabled={!newName.trim()} className="rounded bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50">Add</button>
      </form>

      {error && <p className="text-xs text-red-600 mb-2">{error}</p>}

      <ul className="space-y-1.5">
        {items.map((m) => (
          <li key={m.id} className="py-1">
            <InlineRow
              value={m.name}
              onSave={(name) => updateManager(m.id, name).then(load)}
              onDelete={() => deleteManager(m.id).then(load)}
              placeholder="Manager name"
            />
          </li>
        ))}
        {items.length === 0 && <p className="text-xs text-gray-400">No managers yet</p>}
      </ul>
    </div>
  );
}

// ── Teams Section ────────────────────────────────────────────────

function TeamsSection() {
  const [items, setItems] = useState<Team[]>([]);
  const [managers, setManagers] = useState<Manager[]>([]);
  const [newName, setNewName] = useState('');
  const [managerId, setManagerId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(() => {
    getTeams().then(setItems).catch(() => setItems([]));
    getManagers().then(setManagers).catch(() => setManagers([]));
  }, []);
  useEffect(() => { loadAll(); }, [loadAll]);

  const add = async () => {
    const name = newName.trim();
    if (!name || managerId == null) return;
    setError(null);
    try {
      await createTeam(name, managerId);
      setNewName('');
      loadAll();
    } catch (e: any) { setError(e.message); }
  };

  const resolveManager = (id: number) => managers.find((m) => m.id === id)?.name ?? '—';

  return (
    <div className="bg-white rounded-lg shadow p-5">
      <h2 className="text-base font-semibold text-gray-800 mb-3">Teams</h2>

      <form onSubmit={(e) => { e.preventDefault(); add(); }} className="space-y-2 mb-3">
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Team name"
          className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:ring-blue-500"
        />
        <div className="flex gap-2">
          <select
            value={managerId ?? ''}
            onChange={(e) => setManagerId(e.target.value ? Number(e.target.value) : null)}
            className="flex-1 rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="">Select manager…</option>
            {managers.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
          <button type="submit" disabled={!newName.trim() || managerId == null} className="rounded bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50">Add</button>
        </div>
      </form>

      {error && <p className="text-xs text-red-600 mb-2">{error}</p>}

      <ul className="space-y-1.5">
        {items.map((t) => (
          <li key={t.id} className="py-1">
            <div className="flex items-center gap-2 group">
              <InlineRow
                value={t.name}
                onSave={(name) => updateTeam(t.id, { name }).then(loadAll)}
                onDelete={() => deleteTeam(t.id).then(loadAll)}
                placeholder="Team name"
              />
              <span className="text-[10px] text-gray-400 whitespace-nowrap">{resolveManager(t.manager_id)}</span>
            </div>
          </li>
        ))}
        {items.length === 0 && <p className="text-xs text-gray-400">No teams yet</p>}
      </ul>
    </div>
  );
}

// ── Members Section ──────────────────────────────────────────────

function MembersSection() {
  const [items, setItems] = useState<TeamMember[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [newName, setNewName] = useState('');
  const [teamId, setTeamId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(() => {
    getTeamMembers().then(setItems).catch(() => setItems([]));
    getTeams().then(setTeams).catch(() => setTeams([]));
  }, []);
  useEffect(() => { loadAll(); }, [loadAll]);

  const add = async () => {
    const name = newName.trim();
    if (!name || teamId == null) return;
    setError(null);
    try {
      await createTeamMember(name, teamId);
      setNewName('');
      loadAll();
    } catch (e: any) { setError(e.message); }
  };

  const resolveTeam = (id: number) => teams.find((t) => t.id === id)?.name ?? '—';

  return (
    <div className="bg-white rounded-lg shadow p-5">
      <h2 className="text-base font-semibold text-gray-800 mb-3">Members</h2>

      <form onSubmit={(e) => { e.preventDefault(); add(); }} className="space-y-2 mb-3">
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Member name"
          className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:ring-blue-500"
        />
        <div className="flex gap-2">
          <select
            value={teamId ?? ''}
            onChange={(e) => setTeamId(e.target.value ? Number(e.target.value) : null)}
            className="flex-1 rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="">Select team…</option>
            {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <button type="submit" disabled={!newName.trim() || teamId == null} className="rounded bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50">Add</button>
        </div>
      </form>

      {error && <p className="text-xs text-red-600 mb-2">{error}</p>}

      <ul className="space-y-1.5">
        {items.map((tm) => (
          <li key={tm.id} className="py-1">
            <div className="flex items-center gap-2 group">
              <InlineRow
                value={tm.name}
                onSave={(name) => updateTeamMember(tm.id, { name }).then(loadAll)}
                onDelete={() => deleteTeamMember(tm.id).then(loadAll)}
                placeholder="Member name"
              />
              <span className="text-[10px] text-gray-400 whitespace-nowrap">{resolveTeam(tm.team_id)}</span>
            </div>
          </li>
        ))}
        {items.length === 0 && <p className="text-xs text-gray-400">No members yet</p>}
      </ul>
    </div>
  );
}
