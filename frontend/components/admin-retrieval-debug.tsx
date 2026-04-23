"use client";

import { FormEvent, useEffect, useState, useTransition } from "react";
import { RetrievalDebugResponse, previewRetrieval } from "@/lib/api";
import { AdminShell } from "@/components/admin-shell";

function formatScore(score: number | null) {
  if (score === null) {
    return "n/a";
  }

  return score.toFixed(3);
}

function formatStatus(status: RetrievalDebugResponse["status"]) {
  if (status === "matched") {
    return "Matched";
  }
  if (status === "clarification_required") {
    return "Clarification";
  }
  if (status === "out_of_domain") {
    return "Out of Domain";
  }
  return "Escalated";
}

export function AdminRetrievalDebug() {
  const [question, setQuestion] = useState("У меня дома пропал интернет");
  const [conversationId, setConversationId] = useState("");
  const [result, setResult] = useState<RetrievalDebugResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const query = params.get("query");
    const conversation = params.get("conversation_id");
    if (!query) {
      if (conversation) {
        setConversationId(conversation);
      }
      return;
    }

    setQuestion(query);
    if (conversation) {
      setConversationId(conversation);
    }
    setResult(null);
    setError(null);
  }, []);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) {
      return;
    }

    setError(null);
    startTransition(async () => {
      try {
        const response = await previewRetrieval(trimmed, conversationId || undefined);
        setResult(response);
      } catch (submitError) {
        const detail =
          submitError instanceof Error
            ? submitError.message
            : "Не удалось выполнить debug retrieval.";
        setError(detail);
      }
    });
  };

  return (
    <AdminShell
      activeSection="debug"
      description="Экран для ручной проверки top-k retrieval, score и threshold-решения без записи запроса в историю."
      title="Retrieval Debug"
    >
      <section className="workspaceGrid">
        <section className="surfaceCard inputCard">
          <div className="panelHeading">
            <div>
              <span className="sectionTag">Debug Query</span>
              <h2>Проверка retrieval</h2>
            </div>
          </div>

          <form className="queryForm" onSubmit={handleSubmit}>
            <label className="fieldLabel" htmlFor="debug-question">
              Запрос
            </label>
            <textarea
              id="debug-question"
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Например: Не могу оплатить связь"
              rows={4}
              value={question}
            />
            <label className="fieldLabel" htmlFor="debug-conversation-id">
              Conversation ID
            </label>
            <input
              id="debug-conversation-id"
              onChange={(event) => setConversationId(event.target.value)}
              placeholder="Например: conv_..."
              value={conversationId}
            />
            <div className="formFooter">
              <span className="helperText">
                Backend вернёт contextualized query, recent messages, top-3 кандидата и
                финальный threshold decision.
              </span>
              <button className="primaryButton" disabled={isPending} type="submit">
                {isPending ? "Ищем..." : "Прогнать retrieval"}
              </button>
            </div>
          </form>
        </section>

        <section className="surfaceCard resultCard">
          <div className="panelHeading">
            <div>
              <span className="sectionTag">Decision</span>
              <h2>Итог backend</h2>
            </div>
            {result ? (
              <span
                className={`statusBadge ${
                  result.status === "matched"
                    ? "success"
                    : result.status === "escalated" || result.status === "out_of_domain"
                      ? "warning"
                      : ""
                }`}
              >
                {formatStatus(result.status)}
              </span>
            ) : null}
          </div>

          {error ? <div className="errorBanner">{error}</div> : null}

          {result ? (
            <div className="resultState">
              <div className="resultBody">
                <p className="resultTitle">{result.answer}</p>
              </div>
              <div className="metaGrid">
                <div className="metaItem wide">
                  <span>Исходный запрос</span>
                  <strong>{result.original_question}</strong>
                </div>
                <div className="metaItem wide">
                  <span>Нормализованный запрос</span>
                  <strong>{result.normalized_question}</strong>
                </div>
                <div className="metaItem wide">
                  <span>Contextualized query</span>
                  <strong>{result.contextualized_query}</strong>
                </div>
                <div className="metaItem wide">
                  <span>Normalized contextualized query</span>
                  <strong>{result.normalized_contextualized_query}</strong>
                </div>
                <div className="metaItem">
                  <span>Статус</span>
                  <strong>{result.status}</strong>
                </div>
                <div className="metaItem">
                  <span>Threshold decision</span>
                  <strong>{result.threshold_decision}</strong>
                </div>
                <div className="metaItem">
                  <span>Score</span>
                  <strong>{formatScore(result.score)}</strong>
                </div>
                <div className="metaItem">
                  <span>Threshold</span>
                  <strong>{formatScore(result.threshold)}</strong>
                </div>
                <div className="metaItem">
                  <span>Domain threshold</span>
                  <strong>{formatScore(result.domain_threshold)}</strong>
                </div>
                <div className="metaItem">
                  <span>Domain score</span>
                  <strong>{formatScore(result.domain_score)}</strong>
                </div>
                <div className="metaItem">
                  <span>Follow-up</span>
                  <strong>{result.follow_up_detected ? "Да" : "Нет"}</strong>
                </div>
                <div className="metaItem">
                  <span>Clarification</span>
                  <strong>{result.clarification_triggered ? "Да" : "Нет"}</strong>
                </div>
                <div className="metaItem">
                  <span>Soft match</span>
                  <strong>{result.soft_match_used ? "Да" : "Нет"}</strong>
                </div>
                <div className="metaItem">
                  <span>Margin</span>
                  <strong>{formatScore(result.match_margin)}</strong>
                </div>
                <div className="metaItem wide">
                  <span>Conversation ID</span>
                  <strong>{result.conversation_id || "Не передан"}</strong>
                </div>
                <div className="metaItem wide">
                  <span>Лучшее совпадение</span>
                  <strong>{result.matched_question ?? "Нет кандидата"}</strong>
                </div>
                <div className="metaItem wide">
                  <span>Quick replies</span>
                  <strong>
                    {result.quick_replies.length
                      ? result.quick_replies.map((reply) => `${reply.label} (${reply.type})`).join(" · ")
                      : "Нет"}
                  </strong>
                </div>
                <div className="metaItem wide">
                  <span>Domain reason</span>
                  <strong>{result.domain_reason ?? result.ood_reason ?? "—"}</strong>
                </div>
                <div className="metaItem wide">
                  <span>Soft match reason</span>
                  <strong>{result.soft_match_reason ?? "—"}</strong>
                </div>
                <div className="metaItem wide">
                  <span>Signal hits</span>
                  <strong>
                    {result.domain_keyword_hits.length
                      ? result.domain_keyword_hits.join(" · ")
                      : "Нет keyword hits"}
                  </strong>
                </div>
              </div>
            </div>
          ) : (
            <div className="resultState empty">
              <p className="resultTitle">Пока нет результата</p>
              <p>После запроса здесь появится threshold decision и top-k кандидаты.</p>
            </div>
          )}
        </section>
      </section>

      <section className="surfaceCard tableCard">
        <div className="panelHeading">
          <div>
            <span className="sectionTag">Decision Trace</span>
            <h2>Почему backend принял это решение</h2>
          </div>
        </div>

        <div className="tableWrap">
          <table className="dataTable">
            <thead>
              <tr>
                <th>Type</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {result ? (
                <>
                  {result.domain_signals.map((signal, index) => (
                    <tr key={`signal-${index}`}>
                      <td>Signal</td>
                      <td className="primaryCell">{signal}</td>
                    </tr>
                  ))}
                  {result.decision_path.map((step, index) => (
                    <tr key={`path-${index}`}>
                      <td>Decision path</td>
                      <td className="primaryCell">{step}</td>
                    </tr>
                  ))}
                  <tr>
                    <td>Off-topic rule</td>
                    <td className="primaryCell">{result.offtopic_rule_hit ?? "—"}</td>
                  </tr>
                  <tr>
                    <td>Garbage rule</td>
                    <td className="primaryCell">{result.garbage_rule_hit ?? "—"}</td>
                  </tr>
                </>
              ) : (
                <tr>
                  <td className="emptyTable" colSpan={2}>
                    После retrieval preview здесь появится decision trace.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="surfaceCard tableCard">
        <div className="panelHeading">
          <div>
            <span className="sectionTag">Recent Messages</span>
            <h2>Контекст диалога</h2>
          </div>
        </div>

        <div className="tableWrap">
          <table className="dataTable">
            <thead>
              <tr>
                <th>Role</th>
                <th>Text</th>
                <th>Decision</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {result?.recent_messages.length ? (
                result.recent_messages.map((message, index) => (
                  <tr key={`${message.role}-${index}-${message.created_at}`}>
                    <td>{message.role}</td>
                    <td className="primaryCell">{message.text}</td>
                    <td>{message.decision_type ?? "n/a"}</td>
                    <td>{new Date(message.created_at).toLocaleString()}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="emptyTable" colSpan={4}>
                    Нет сохранённого dialogue context для этого preview.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="surfaceCard tableCard">
        <div className="panelHeading">
          <div>
            <span className="sectionTag">Top Matches</span>
            <h2>Top-3 похожих FAQ</h2>
          </div>
        </div>

        <div className="tableWrap">
          <table className="dataTable">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Canonical FAQ</th>
                <th>Matched variant</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {result?.top_matches.length ? (
                result.top_matches.map((match, index) => (
                  <tr key={`${match.faq_id}-${index}`}>
                    <td>{index + 1}</td>
                    <td className="primaryCell">{match.canonical_question}</td>
                    <td>{match.matched_question}</td>
                    <td>{formatScore(match.score)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="emptyTable" colSpan={4}>
                    Нет top-k данных. Выполните retrieval-запрос.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </AdminShell>
  );
}
