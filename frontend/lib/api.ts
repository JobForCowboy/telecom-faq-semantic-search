export type ChatResponse = {
  status: "matched" | "fallback";
  answer: string;
  similarity_score: number | null;
  matched_faq_id: number | null;
  matched_question: string | null;
};

export type FAQItem = {
  id: number;
  question: string;
  answer: string;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
};

export type EscalationItem = {
  id: number;
  question_text: string;
  response_text: string;
  similarity_score: number | null;
  created_at: string;
};

type FAQPayload = {
  question: string;
  answer: string;
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
