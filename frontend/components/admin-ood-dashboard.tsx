"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { OutOfDomainItem, fetchOutOfDomain } from "@/lib/api";
import { AdminShell } from "@/components/admin-shell";

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(value));
}

function formatScore(score: number | null) {
  if (score === null) {
    return "n/a";
  }
  return score.toFixed(3);
}

function summarizeTopMatches(item: OutOfDomainItem) {
  if (!item.retrieval_candidates.length) {
    return "Нет retrieval candidates";
  }

  return item.retrieval_candidates
    .slice(0, 2)
    .map((candidate, index) => {
      const canonical = String(candidate.canonical_question ?? "FAQ");
      const score = typeof candidate.score === "number" ? candidate.score.toFixed(3) : "n/a";
      return `${index + 1}. ${canonical} (${score})`;
    })
    .join(" · ");
}

function summarizeSignals(item: OutOfDomainItem) {
  const parts = [
    item.ood_reason,
    item.offtopic_rule_hit ? `off-topic: ${item.offtopic_rule_hit}` : null,
    item.garbage_rule_hit ? `garbage: ${item.garbage_rule_hit}` : null
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Нет явной причины";
}

export function AdminOodDashboard() {
  const [items, setItems] = useState<OutOfDomainItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOutOfDomain()
      .then(setItems)
      .catch((loadError) => {
        const detail =
          loadError instanceof Error
            ? loadError.message
            : "Не удалось загрузить out-of-domain запросы.";
        setError(detail);
      });
  }, []);

  const summary = useMemo(() => {
    return {
      total: items.length,
      withOfftopicRule: items.filter((item) => item.offtopic_rule_hit).length,
      withKeywordHits: items.filter((item) => item.domain_keyword_hits.length > 0).length
    };
  }, [items]);

  return (
    <AdminShell
      activeSection="out_of_domain"
      description="Отдельный экран для запросов, которые система сочла вне telecom-domain и не отправила оператору."
      title="Out-of-Domain Review"
    >
      <section className="adminToolbar">
        <div className="statsRow">
          <div className="metricCard">
            <span>Всего OOD</span>
            <strong>{summary.total}</strong>
          </div>
          <div className="metricCard">
            <span>С off-topic правилом</span>
            <strong>{summary.withOfftopicRule}</strong>
          </div>
          <div className="metricCard">
            <span>С domain keyword hit</span>
            <strong>{summary.withKeywordHits}</strong>
          </div>
        </div>
      </section>

      {error ? <div className="errorBanner">{error}</div> : null}

      <section className="surfaceCard tableCard">
        <div className="panelHeading">
          <div>
            <span className="sectionTag">Domain Filter</span>
            <h2>Запросы вне домена</h2>
          </div>
        </div>

        <div className="tableWrap">
          <table className="dataTable">
            <thead>
              <tr>
                <th>ID</th>
                <th>Вопрос</th>
                <th>Нормализация</th>
                <th>Domain score</th>
                <th>Причина</th>
                <th>Top retrieval</th>
                <th>Debug</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td className="emptyTable" colSpan={8}>
                    Пока нет запросов, помеченных как out_of_domain.
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td className="primaryCell">{item.question_text}</td>
                    <td>{item.normalized_question_text}</td>
                    <td>{formatScore(item.domain_score)}</td>
                    <td>{summarizeSignals(item)}</td>
                    <td>{summarizeTopMatches(item)}</td>
                    <td>
                      <Link
                        className="tableButton"
                        href={`/admin/debug?query=${encodeURIComponent(item.question_text)}`}
                      >
                        Debug
                      </Link>
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
