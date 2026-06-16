import type { Source } from "../types";

interface Props {
  source: Source;
  index: number;
}

export default function SourceCard({ source, index }: Props) {
  return (
    <details className="border border-gray-700 rounded-lg overflow-hidden">
      <summary className="px-3 py-2 bg-gray-800 cursor-pointer text-sm font-medium text-gray-300 hover:bg-gray-750">
        #{index + 1} — {source.source.split("/").pop()}
        {source.page != null && <span className="ml-2 text-gray-500">p.{source.page}</span>}
      </summary>
      <p className="p-3 text-sm text-gray-400 leading-relaxed whitespace-pre-wrap">
        {source.content}
      </p>
    </details>
  );
}
