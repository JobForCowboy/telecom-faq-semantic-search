export type RetrievalMatch = {
  faq_id: number;
  canonical_question: string;
  matched_question: string;
  score: number;
};

export type ChatResponse = {
  status: "matched" | "escalated";
  answer: string;
  score: number | null;
  matched_faq_id: number | null;
  matched_question: string | null;
  top_matches: RetrievalMatch[];
};

export type RetrievalDebugResponse = ChatResponse & {
  original_question: string;
  normalized_question: string;
  threshold: number;
};

export type FAQItem = {
  id: number;
  canonical_question: string;
  answer: string;
  variants: string[];
  is_active: boolean;
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

export function queryChat(question: string) {
  return apiFetch<ChatResponse>("/api/chat/query", {
    method: "POST",
    body: JSON.stringify({ question })
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

export function previewRetrieval(question: string) {
  return apiFetch<RetrievalDebugResponse>("/api/admin/retrieval-debug", {
    method: "POST",
    body: JSON.stringify({ question })
  });
}
