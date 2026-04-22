"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { EscalationItem, fetchEscalations } from "@/lib/api";
import { AdminShell } from "@/components/admin-shell";

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(value));
}

function formatSimilarity(score: number | null) {
  if (score === null) {
    return "n/a";
  }

  return score.toFixed(3);
}

function trimPreview(text: string, maxLength = 140) {
  if (text.length <= maxLength) {
    return text;
  }

  return `${text.slice(0, maxLength).trim()}…`;
}

export function AdminEscalationsDashboard() {
  const [items, setItems] = useState<EscalationItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchEscalations()
      .then(setItems)
      .catch((loadError) => {
        const detail =
          loadError instanceof Error
            ? loadError.message
            : "Не удалось загрузить эскалации.";
        setError(detail);
      });
  }, []);

  const summary = useMemo(() => {
    return {
      total: items.length,
      withScore: items.filter((item) => item.score !== null).length,
      lastCreatedAt: items[0]?.created_at ?? null
    };
  }, [items]);

  return (
    <AdminShell
      activeSection="escalations"
      description="Отдельный экран для анализа запросов, которые не прошли по порогу уверенности."
      title="Escalation Review"
    >
      <section className="adminToolbar">
        <div className="statsRow">
          <div className="metricCard">
            <span>Всего эскалаций</span>
            <strong>{summary.total}</strong>
          </div>
          <div className="metricCard">
            <span>Со score</span>
            <strong>{summary.withScore}</strong>
          </div>
          <div className="metricCard">
            <span>Последняя запись</span>
            <strong>
              {summary.lastCreatedAt ? formatDateTime(summary.lastCreatedAt) : "—"}
            </strong>
          </div>
        </div>
      </section>

      {error ? <div className="errorBanner">{error}</div> : null}

      <section className="surfaceCard tableCard">
        <div className="panelHeading">
          <div>
            <span className="sectionTag">Fallback queue</span>
            <h2>Эскалированные запросы</h2>
          </div>
        </div>

        <div className="tableWrap">
          <table className="dataTable">
            <thead>
              <tr>
                <th>ID</th>
                <th>Вопрос</th>
                <th>Нормализация</th>
                <th>Ответ системы</th>
                <th>Score</th>
                <th>Лучший FAQ</th>
                <th>Следующий шаг</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td className="emptyTable" colSpan={8}>
                    Пока нет запросов, отправленных на ручную обработку.
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td className="primaryCell">{item.question_text}</td>
                    <td>{trimPreview(item.normalized_question_text)}</td>
                    <td>
                      <div className="previewCell">{trimPreview(item.response_text)}</div>
                    </td>
                    <td>{formatSimilarity(item.score)}</td>
                    <td>
                      {item.matched_canonical_question
                        ? `#${item.matched_faq_id}: ${item.matched_canonical_question}`
                        : "—"}
                    </td>
                    <td>
                      <div className="tableActions">
                        <Link
                          className="tableButton"
                          href={`/admin/debug?query=${encodeURIComponent(item.question_text)}`}
                        >
                          Debug
                        </Link>
                        <span className="helperText">
                          {item.matched_faq_id
                            ? "Похоже на новый variant"
                            : "Похоже на новый canonical FAQ"}
                        </span>
                      </div>
                    </td>
                    <td>{formatDateTime(item.created_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </AdminShell>
  );
}
