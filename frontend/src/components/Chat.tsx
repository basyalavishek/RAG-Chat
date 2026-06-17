import { useState, useRef, useEffect } from "react";
import { Send, Bot, User } from "lucide-react";
import { queryStream, sessionQueryStream, getMessages, addMessage } from "../api/client";
import type { Message } from "../types";
import SourceCard from "./SourceCard";

interface Props {
  sessionId: string | null;
}

export default function Chat({ sessionId }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (sessionId) {
      getMessages(sessionId).then(setMessages).catch(() => setMessages([]));
    } else {
      setMessages([]);
    }
  }, [sessionId]);

  const handleSend = async () => {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setLoading(true);

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: q };
    const assistantId = crypto.randomUUID();
    const assistantMsg: Message = { id: assistantId, role: "assistant", content: "" };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    if (sessionId) {
      addMessage(sessionId, "user", q).catch(() => {});
    }

    try {
      let full = "";
      const stream = sessionId
        ? sessionQueryStream(sessionId, q, (chunk) => { full += chunk; update(full); }, () => {})
        : queryStream(q, (chunk) => { full += chunk; update(full); }, () => {});
      await stream;

      if (sessionId && full) {
        addMessage(sessionId, "assistant", full).catch(() => {});
      }
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: `Error: ${err.message}` } : m
        )
      );
    } finally {
      setLoading(false);
    }

    function update(text: string) {
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, content: text } : m))
      );
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto space-y-4 px-4 py-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <Bot size={40} className="mb-3" />
            <p className="text-lg font-medium">Ask anything about your documents</p>
            <p className="text-sm mt-1">Upload PDFs, text files, or markdown to get started</p>
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>
            {m.role === "assistant" && (
              <div className="shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center mt-1">
                <Bot size={16} />
              </div>
            )}

            <div className={`max-w-[75%] ${m.role === "user" ? "order-first" : ""}`}>
              <div
                className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                  m.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-200"
                }`}
              >
                {m.content}
              </div>

              {m.sources && m.sources.length > 0 && (
                <div className="mt-2 space-y-1.5">
                  <p className="text-xs text-gray-500 font-medium ml-1">Sources</p>
                  {m.sources.map((s, i) => (
                    <SourceCard key={i} source={s} index={i} />
                  ))}
                </div>
              )}
            </div>

            {m.role === "user" && (
              <div className="shrink-0 w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center mt-1">
                <User size={16} />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
              <Bot size={16} />
            </div>
            <div className="bg-gray-800 rounded-2xl px-4 py-3">
              <span className="animate-pulse text-gray-400">Thinking...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-gray-800 px-4 py-3">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your documents..."
            rows={1}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm resize-none outline-none focus:border-blue-500 transition-colors placeholder-gray-500"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
