import { apiClient } from "./client";

export interface DocumentChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface DocumentChatResponse {
  status: "answered" | "indexing" | "no_document";
  answer: string | null;
  message: string | null;
}

/** Hỏi-đáp tự do về tài liệu gốc đã dùng để tạo lộ trình — trả lời bằng RAG, không bịa ngoài tài
 * liệu. `history`: tối đa vài tin nhắn gần nhất để giữ mạch hội thoại (server không lưu gì). */
export async function sendDocumentChatMessage(
  roadmapId: string,
  question: string,
  history: DocumentChatMessage[]
): Promise<DocumentChatResponse> {
  const response = await apiClient.post(`/learners/me/roadmaps/${roadmapId}/document-chat`, {
    question,
    history,
  });
  return response.data;
}
