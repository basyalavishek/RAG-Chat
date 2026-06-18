import { useState, useEffect, useCallback, useRef } from "react";
import { Plus, Library, MessageSquare, Trash2, Check, X } from "lucide-react";
import Chat from "./components/Chat";
import DocumentUpload from "./components/DocumentUpload";
import { listSessions, createSession, deleteSession, renameSession } from "./api/client";
import type { Session } from "./types";

// switching between chats, renaming a chat title, and deleting a chat session.
function SessionItem({ s, active, onSelect, onDelete, onRename }: {
  s: Session;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (name: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(s.name);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const save = () => {
    const trimmed = val.trim();
    if (trimmed && trimmed !== s.name) onRename(trimmed);
    else setVal(s.name);
    setEditing(false);
  };

  return (
    <div
      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors group ${
        active ? "bg-gray-700 text-white" : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
      }`}
    >
      <MessageSquare size={14} className="shrink-0" />
      {editing ? (
        <div className="flex-1 flex items-center gap-1">
          <input
            ref={inputRef}
            value={val}
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") { setVal(s.name); setEditing(false); } }}
            className="flex-1 bg-gray-900 border border-gray-600 rounded px-1.5 py-0.5 text-xs outline-none"
          />
          <button onClick={save} className="text-green-400 hover:text-green-300"><Check size={12} /></button>
          <button onClick={() => { setVal(s.name); setEditing(false); }} className="text-gray-500 hover:text-gray-300"><X size={12} /></button>
        </div>
      ) : (
        <button onClick={onSelect} className="truncate flex-1 text-left">{s.name}</button>
      )}
      {!editing && (
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
          <button
            onClick={() => { setVal(s.name); setEditing(true); }}
            className="text-gray-500 hover:text-blue-400"
          >
            <span className="text-[10px]">edit</span>
          </button>
          <button onClick={onDelete} className="text-gray-500 hover:text-red-400">
            <Trash2 size={12} />
          </button>
        </div>
      )}
    </div>
  );
}


export default function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    try {
      const list = await listSessions();
      setSessions(list);
    } catch {
      setSessions([]);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (!activeId && sessions.length > 0) {
      setActiveId(sessions[sessions.length - 1].id);
    }
  }, [sessions, activeId]);

  const handleNew = async () => {
    const s = await createSession();
    setSessions((prev) => [...prev, s]);
    setActiveId(s.id);
  };

  const handleDelete = async (id: string) => {
    await deleteSession(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (activeId === id) setActiveId(null);
  };

  const handleRename = async (id: string, name: string) => {
    const updated = await renameSession(id, name);
    setSessions((prev) => prev.map((s) => (s.id === id ? updated : s)));
  };

  return (
    <div className="h-screen flex flex-col max-w-6xl mx-auto">
      <header className="flex items-center justify-between px-6 py-3 border-b border-gray-800 shrink-0">
        <div className="flex items-center gap-2">
          <Library size={22} className="text-blue-400" />
          <h1 className="text-lg font-semibold">RAG Chat</h1>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <aside className="w-72 border-r border-gray-800 flex flex-col shrink-0 hidden md:flex">
          <div className="p-3 border-b border-gray-800">
            <button
              onClick={handleNew}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
            >
              <Plus size={16} />
              New Chat
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {sessions.map((s) => (
              <SessionItem
                key={s.id}
                s={s}
                active={s.id === activeId}
                onSelect={() => setActiveId(s.id)}
                onDelete={() => handleDelete(s.id)}
                onRename={(name) => handleRename(s.id, name)}
              />
            ))}
          </div>

          <div className="border-t border-gray-800 p-3 space-y-3">
            <DocumentUpload sessionId={activeId} onStatsChange={loadSessions} />
          </div>
        </aside>

        <Chat sessionId={activeId} />
      </div>
    </div>
  );
}
