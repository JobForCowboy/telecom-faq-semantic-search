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

export function AdminRetrievalDebug() {
  const [question, setQuestion] = useState("У меня дома пропал интернет");
  const [result, setResult] = useState<RetrievalDebugResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const query = params.get("query");
    if (!query) {
      return;
    }

    setQuestion(query);
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
        const response = await previewRetrieval(trimmed);
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
            <div className="formFooter">
              <span className="helperText">
                Backend вернёт top-3 кандидата и финальный статус threshold decision.
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
                className={`statusBadge ${result.status === "matched" ? "success" : "warning"}`}
              >
                {result.status === "matched" ? "Matched" : "Escalated"}
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
                <div className="metaItem">
                  <span>Статус</span>
                  <strong>{result.status}</strong>
                </div>
                <div className="metaItem">
                  <span>Score</span>
                  <strong>{formatScore(result.score)}</strong>
                </div>
                <div className="metaItem">
                  <span>Threshold</span>
                  <strong>{formatScore(result.threshold)}</strong>
                </div>
                <div className="metaItem wide">
                  <span>Лучшее совпадение</span>
                  <strong>{result.matched_question ?? "Нет кандидата"}</strong>
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
