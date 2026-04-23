export type RetrievalMatch = {
  faq_id: number;
  canonical_question: string;
  matched_question: string;
  score: number;
};

export type QuickReply = {
  type: "clarification" | "intent_hypothesis" | "followup" | "fallback";
  label: string;
  value: string;
};

export type ConversationMessage = {
  role: "user" | "assistant";
  text: string;
  created_at: string;
  decision_type: "matched" | "clarification_required" | "escalated" | null;
};

export type ChatResponse = {
  status: "matched" | "clarification_required" | "escalated";
  answer: string;
  score: number | null;
  matched_faq_id: number | null;
  matched_question: string | null;
  top_matches: RetrievalMatch[];
  conversation_id: string;
  conversation_message_count: number;
  is_follow_up: boolean;
  clarification_question: string | null;
  clarification_type: string | null;
  quick_replies: QuickReply[];
};

export type RetrievalDebugResponse = ChatResponse & {
  original_question: string;
  normalized_question: string;
  raw_query: string;
  contextualized_query: string;
  normalized_contextualized_query: string;
  threshold: number;
  recent_messages: ConversationMessage[];
  follow_up_detected: boolean;
  clarification_triggered: boolean;
  threshold_decision: "matched" | "clarification_required" | "escalated";
};

export type ResetConversationResponse = {
  conversation_id: string;
  cleared: boolean;
  message_count: number;
};

export type FAQItem = {
  id: number;
  canonical_question: string;
  answer: string;
  variants: string[];
  is_active: boolean;
  intent_tag: string | null;
  intent_label: string | null;
  created_at: string;
  updated_at: string | null;
};

export type EscalationItem = {
  id: number;
  question_text: string;
  normalized_question_text: string;
  response_text: string;
  score: number | null;
  matched_faq_id: number | null;
  matched_canonical_question: string | null;
  created_at: string;
};

type FAQPayload = {
  canonical_question: string;
  answer: string;
  variants: string[];
  is_active: boolean;
  intent_tag?: string | null;
  intent_label?: string | null;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const detail = await response
      .json()
      .then((payload) => payload.detail as string | undefined)
      .catch(() => undefined);
    throw new Error(detail ?? `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function queryChat(question: string, conversationId?: string | null) {
  return apiFetch<ChatResponse>("/api/chat/query", {
    method: "POST",
    body: JSON.stringify({
      question,
      ...(conversationId ? { conversation_id: conversationId } : {})
    })
  });
}

export function resetConversation(conversationId?: string | null) {
  return apiFetch<ResetConversationResponse>("/api/chat/reset", {
    method: "POST",
    body: JSON.stringify(
      conversationId ? { conversation_id: conversationId } : {}
    )
  });
}

export function fetchFaqs() {
  return apiFetch<FAQItem[]>("/api/admin/faqs");
}

export function createFaq(payload: FAQPayload) {
  return apiFetch<FAQItem>("/api/admin/faqs", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateFaq(faqId: number, payload: FAQPayload) {
  return apiFetch<FAQItem>(`/api/admin/faqs/${faqId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function deleteFaq(faqId: number) {
  return apiFetch<void>(`/api/admin/faqs/${faqId}`, {
    method: "DELETE"
  });
}

export function fetchEscalations() {
  return apiFetch<EscalationItem[]>("/api/admin/escalations");
}

export function previewRetrieval(question: string, conversationId?: string | null) {
  return apiFetch<RetrievalDebugResponse>("/api/admin/retrieval-debug", {
    method: "POST",
    body: JSON.stringify({
      question,
      ...(conversationId ? { conversation_id: conversationId } : {})
    })
  });
}
