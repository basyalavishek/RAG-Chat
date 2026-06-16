export interface Source {
  content: string;
  source: string;
  page?: number;
}

export interface QueryResponse {
  answer: string;
  sources: Source[];
}

export interface StatsResponse {
  total_documents: number;
}

export interface IngestResponse {
  filename: string;
  chunks: number;
  total_documents: number;
}

export type MessageRole = "user" | "assistant";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  sources?: Source[];
}

export interface Session {
  id: string;
  name: string;
  created_at: string;
  filenames: string[];
}
