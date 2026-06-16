import { useState, useRef } from "react";
import { Upload, FileText, Check, Loader2, Trash2 } from "lucide-react";
import { sessionIngestFile, sessionClear, ingestFile, clearDocuments } from "../api/client";

interface Props {
  sessionId: string | null;
  onStatsChange: () => void;
}

export default function DocumentUpload({ sessionId, onStatsChange }: Props) {
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMsg(null);
    try {
      const ingest = sessionId ? sessionIngestFile : ingestFile;
      const res = await (sessionId ? sessionIngestFile(sessionId, file) : ingestFile(file));
      setMsg({ ok: true, text: `"${res.filename}" — ${res.chunks} chunks indexed` });
      onStatsChange();
    } catch (err: any) {
      setMsg({ ok: false, text: err.message });
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const handleClear = async () => {
    if (!confirm("Delete all documents in this session?")) return;
    try {
      if (sessionId) {
        await sessionClear(sessionId);
      } else {
        await clearDocuments();
      }
      setMsg({ ok: true, text: "Documents cleared" });
      onStatsChange();
    } catch (err: any) {
      setMsg({ ok: false, text: err.message });
    }
  };

  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 px-4 py-2.5 border-2 border-dashed border-gray-600 rounded-xl cursor-pointer hover:border-blue-500 transition-colors">
        <Upload size={18} className="text-gray-400" />
        <span className="text-sm text-gray-400">
          {uploading ? "Uploading..." : "Upload PDF, TXT, or MD"}
        </span>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,.md,.rst"
          onChange={handleUpload}
          className="hidden"
          disabled={uploading}
        />
        {uploading && <Loader2 size={16} className="animate-spin ml-auto" />}
        {!uploading && <FileText size={16} className="ml-auto text-gray-500" />}
      </label>

      {msg && (
        <div
          className={`flex items-start gap-2 text-sm px-3 py-2 rounded-lg ${
            msg.ok ? "bg-emerald-900/40 text-emerald-300" : "bg-red-900/40 text-red-300"
          }`}
        >
          {msg.ok ? <Check size={14} className="mt-0.5 shrink-0" /> : null}
          <span>{msg.text}</span>
        </div>
      )}

      <button
        onClick={handleClear}
        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-red-400 transition-colors"
      >
        <Trash2 size={12} />
        Clear session documents
      </button>
    </div>
  );
}
