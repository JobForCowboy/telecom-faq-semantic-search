"use client";

import { FormEvent, useMemo, useState, useTransition } from "react";
import { ChatResponse, queryChat } from "@/lib/api";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  meta?: string;
};

const starterPrompts = [
  "Почему не работает интернет дома?",
  "Как оплатить услуги связи?",
  "Как сменить тариф на мобильную связь?"
];

export function ChatShell() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "Опишите проблему с интернетом, тарифом, оплатой или качеством связи. Сервис найдёт готовый ответ из базы знаний.",
      meta: "Semantic search по FAQ-базе"
    }
  ]);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const canSubmit = question.trim().length >= 3 && !isPending;
  const suggestionCards = useMemo(
    () =>
      starterPrompts.map((prompt) => (
        <button
          className="promptCard"
          key={prompt}
          onClick={() => setQuestion(prompt)}
          type="button"
        >
          {prompt}
        </button>
      )),
    []
  );

  const appendAssistantReply = (response: ChatResponse) => {
    const meta =
      response.status === "matched"
        ? `Совпадение: ${Math.round((response.similarity_score ?? 0) * 100)}%`
        : "Низкая уверенность, выполнена эскалация";

    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        text: response.answer,
        meta
      }
    ]);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) {
      return;
    }

    setError(null);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", text: trimmed }
    ]);
    setQuestion("");

    startTransition(async () => {
      try {
        const response = await queryChat(trimmed);
        appendAssistantReply(response);
      } catch (submitError) {
        const detail =
          submitError instanceof Error
            ? submitError.message
            : "Не удалось получить ответ от backend.";
        setError(detail);
      }
    });
  };

  return (
    <main className="pageShell">
      <section className="heroPanel">
        <div className="badge">Telecom Support v1</div>
        <h1>Чат поддержки на semantic search</h1>
        <p>
          Вопрос пользователя кодируется в embedding, сравнивается с FAQ-базой и
          возвращает готовый ответ только при достаточной уверенности.
        </p>
        <div className="promptGrid">{suggestionCards}</div>
      </section>

      <section className="chatPanel">
        <div className="chatHeader">
          <div>
            <span className="eyebrow">Чат</span>
            <h2>Задайте вопрос</h2>
          </div>
          <a className="adminLink" href="/admin">
            Локальная админка FAQ
          </a>
        </div>

        <div className="messageList">
          {messages.map((message) => (
            <article
              className={`messageBubble ${message.role}`}
              key={message.id}
            >
              <p>{message.text}</p>
              {message.meta ? <span>{message.meta}</span> : null}
            </article>
          ))}
          {error ? <div className="errorBanner">{error}</div> : null}
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Например: У меня пропал домашний интернет"
            rows={3}
            value={question}
          />
          <button disabled={!canSubmit} type="submit">
            {isPending ? "Идёт поиск..." : "Найти ответ"}
          </button>
        </form>
      </section>
    </main>
  );
}

