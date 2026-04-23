"use client";

import { FormEvent, useEffect, useRef, useState, useTransition } from "react";
import { ChatResponse, QuickReply, queryChat, resetConversation } from "@/lib/api";

const starterPrompts = [
  "инет дома не работает",
  "не работает интернет",
  "не могу зайти в лк",
  "как оплатить связь"
];

const CONVERSATION_ID_KEY = "telecom-faq-conversation-id";
const LAST_RESPONSE_KEY = "telecom-faq-last-response";
const MESSAGES_KEY = "telecom-faq-messages";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  status?: ChatResponse["status"];
};

function formatStatus(status: ChatResponse["status"]) {
  if (status === "matched") {
    return "Готовый FAQ";
  }
  if (status === "clarification_required") {
    return "Нужно уточнение";
  }
  if (status === "out_of_domain") {
    return "Вне домена";
  }
  return "Передано на эскалацию";
}

function buildAssistantMessage(response: ChatResponse): ChatMessage {
  return {
    id: `assistant-${response.conversation_message_count}-${Date.now()}`,
    role: "assistant",
    text: response.answer,
    status: response.status
  };
}

function buildUserMessage(question: string): ChatMessage {
  return {
    id: `user-${Date.now()}`,
    role: "user",
    text: question
  };
}

function buildStarterReplies(): QuickReply[] {
  return starterPrompts.map((prompt) => ({
    type: "fallback",
    label: prompt,
    value: prompt
  }));
}

export function ChatShell() {
  const [question, setQuestion] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const transcriptRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const storedConversationId = window.sessionStorage.getItem(CONVERSATION_ID_KEY);
    const storedMessages = window.sessionStorage.getItem(MESSAGES_KEY);
    const storedLastResponse = window.sessionStorage.getItem(LAST_RESPONSE_KEY);

    if (storedConversationId) {
      setConversationId(storedConversationId);
    }
    if (storedMessages) {
      try {
        const parsed = JSON.parse(storedMessages) as ChatMessage[];
        setMessages(parsed);
      } catch {
        window.sessionStorage.removeItem(MESSAGES_KEY);
      }
    }
    if (storedLastResponse) {
      try {
        const parsed = JSON.parse(storedLastResponse) as ChatResponse;
        setLastResponse(parsed);
      } catch {
        window.sessionStorage.removeItem(LAST_RESPONSE_KEY);
      }
    }
  }, []);

  useEffect(() => {
    if (conversationId) {
      window.sessionStorage.setItem(CONVERSATION_ID_KEY, conversationId);
    } else {
      window.sessionStorage.removeItem(CONVERSATION_ID_KEY);
    }
  }, [conversationId]);

  useEffect(() => {
    if (messages.length) {
      window.sessionStorage.setItem(MESSAGES_KEY, JSON.stringify(messages));
    } else {
      window.sessionStorage.removeItem(MESSAGES_KEY);
    }
  }, [messages]);

  useEffect(() => {
    if (lastResponse) {
      window.sessionStorage.setItem(LAST_RESPONSE_KEY, JSON.stringify(lastResponse));
    } else {
      window.sessionStorage.removeItem(LAST_RESPONSE_KEY);
    }
  }, [lastResponse]);

  useEffect(() => {
    const transcript = transcriptRef.current;
    if (!transcript) {
      return;
    }

    transcript.scrollTo({
      top: transcript.scrollHeight,
      behavior: "smooth"
    });
  }, [messages, pendingQuestion]);

  const canSubmit = question.trim().length >= 1 && !isPending;
  const starterReplies = buildStarterReplies();
  const visibleQuickReplies = lastResponse?.quick_replies ?? [];

  const submitQuestion = (rawQuestion: string) => {
    const trimmed = rawQuestion.trim();
    if (!trimmed || isPending) {
      return;
    }

    setError(null);
    setPendingQuestion(trimmed);

    startTransition(async () => {
      try {
        const response = await queryChat(trimmed, conversationId);
        setConversationId(response.conversation_id);
        setMessages((current) => [
          ...current,
          buildUserMessage(trimmed),
          buildAssistantMessage(response)
        ]);
        setLastResponse(response);
        setQuestion("");
      } catch (submitError) {
        const detail =
          submitError instanceof Error
            ? submitError.message
            : "Не удалось получить ответ от backend.";
        setError(detail);
      } finally {
        setPendingQuestion(null);
      }
    });
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitQuestion(question);
  };

  const handleReset = () => {
    setError(null);

    startTransition(async () => {
      try {
        const response = await resetConversation(conversationId);
        setConversationId(response.conversation_id);
        setMessages([]);
        setLastResponse(null);
        setPendingQuestion(null);
        setQuestion("");
      } catch (resetError) {
        const detail =
          resetError instanceof Error
            ? resetError.message
            : "Не удалось сбросить диалог.";
        setError(detail);
      }
    });
  };

  const latestAssistantMessageId =
    [...messages].reverse().find((message) => message.role === "assistant")?.id ?? null;

  return (
    <main className="appShell demoShell">
      <header className="topBar demoTopBar">
        <div>
          <span className="sectionTag">Telecom Support</span>
          <h1 className="pageTitle">FAQ Semantic Search</h1>
          <p className="subtleText">
            Короткий диалоговый интерфейс для вопросов про интернет, оплату и личный кабинет.
          </p>
        </div>
        <div className="statusRow">
          <span className="statusBadge">Retrieval-first demo</span>
        </div>
      </header>

      <section className="demoGrid">
        <section className="surfaceCard chatPane">
          <div className="chatPaneHeader">
            <div>
              <span className="sectionTag">Dialogue FAQ</span>
              <h2 className="paneTitle">Спросите как обычному оператору</h2>
              <p className="paneSubtitle">
                Задайте вопрос в свободной форме и продолжайте коротким follow-up сообщением.
              </p>
            </div>
          </div>

          {error ? <div className="errorBanner inlineError">{error}</div> : null}

          <div className="chatPaneBody">
            <div className="chatTranscriptFrame">
              <div className="chatTranscript chatTranscriptViewport" ref={transcriptRef}>
                {messages.length ? (
                  messages.map((message) => (
                    <article
                      className={`chatBubble ${message.role === "assistant" ? "assistant" : "user"}`}
                      key={message.id}
                    >
                      {message.role === "assistant" &&
                      message.status &&
                      message.id === latestAssistantMessageId ? (
                        <span
                          className={`statusBadge messageStatusBadge ${
                            message.status === "matched"
                              ? "success"
                              : message.status === "escalated" || message.status === "out_of_domain"
                                ? "warning"
                                : ""
                          }`}
                        >
                          {formatStatus(message.status)}
                        </span>
                      ) : (
                        <span className="sectionTag muted">
                          {message.role === "assistant" ? "assistant" : "user"}
                        </span>
                      )}
                      <p>{message.text}</p>
                    </article>
                  ))
                ) : (
                  <div className="chatEmptyState">
                    <p className="resultTitle">Задайте вопрос в одну-две фразы</p>
                    <p>Можно начать с примера ниже или сразу написать свой запрос в composer.</p>
                    <div className="chipWrap quickReplyWrap emptyStateChips">
                      {starterReplies.map((reply) => (
                        <button
                          className="suggestionChip quickReplyChip quickReplyChip-fallback"
                          disabled={isPending}
                          key={`${reply.type}-${reply.label}-${reply.value}`}
                          onClick={() => submitQuestion(reply.value)}
                          type="button"
                        >
                          {reply.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {pendingQuestion ? (
                  <article className="chatBubble user pending">
                    <span className="sectionTag muted">user</span>
                    <p>{pendingQuestion}</p>
                  </article>
                ) : null}
              </div>

              {isPending ? (
                <div className="inlineStatusCard">
                  <p className="resultTitle">Подбираем ответ...</p>
                  <p>Учитываем текущий контекст диалога и доступные варианты ответа.</p>
                </div>
              ) : null}
            </div>

            {messages.length > 0 && visibleQuickReplies.length ? (
              <div className="quickReplySection">
                <div className="quickReplyHeader">
                  <span className="sectionTag muted">Быстрый ответ</span>
                </div>
                <div className="chipWrap quickReplyWrap">
                  {visibleQuickReplies.map((reply) => (
                    <button
                      className={`suggestionChip quickReplyChip quickReplyChip-${reply.type}`}
                      disabled={isPending}
                      key={`${reply.type}-${reply.label}-${reply.value}`}
                      onClick={() => submitQuestion(reply.value)}
                      type="button"
                    >
                      {reply.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <form className="chatComposerModule" onSubmit={handleSubmit}>
              <label className="fieldLabel" htmlFor="support-question">
                Сообщение
              </label>
              <div className="composerCard">
                <textarea
                  className="composerTextarea"
                  id="support-question"
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="Например: Не работает интернет"
                  rows={3}
                  value={question}
                />
                <div className="composerActions">
                  <button
                    className="secondaryButton composerReset"
                    disabled={isPending}
                    onClick={handleReset}
                    type="button"
                  >
                    Сбросить
                  </button>
                  <button className="primaryButton composerSend" disabled={!canSubmit} type="submit">
                    {isPending ? "Идёт поиск..." : "Отправить"}
                  </button>
                </div>
              </div>
              <p className="helperText composerHint">
                Короткие follow-up реплики тоже работают: `домашний`, `да`, `в приложении`.
              </p>
            </form>
          </div>
        </section>
      </section>
    </main>
  );
}
