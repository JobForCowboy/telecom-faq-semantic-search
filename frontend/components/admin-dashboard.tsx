"use client";

import { FormEvent, useEffect, useMemo, useState, useTransition } from "react";
import { FAQItem, createFaq, deleteFaq, fetchFaqs, updateFaq } from "@/lib/api";
import { AdminShell } from "@/components/admin-shell";

const emptyForm = {
  canonical_question: "",
  answer: "",
  variants_text: "",
  is_active: true
};

function formatDateTime(value: string | null) {
  if (!value) {
    return "—";
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(value));
}

function trimPreview(text: string, maxLength = 120) {
  if (text.length <= maxLength) {
    return text;
  }

  return `${text.slice(0, maxLength).trim()}…`;
}

export function AdminDashboard() {
  const [faqs, setFaqs] = useState<FAQItem[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editingFaqId, setEditingFaqId] = useState<number | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const loadFaqs = async () => {
    const faqRows = await fetchFaqs();
    setFaqs(faqRows);
  };

  useEffect(() => {
    loadFaqs().catch((loadError) => {
      const detail =
        loadError instanceof Error
          ? loadError.message
          : "Не удалось загрузить FAQ.";
      setError(detail);
    });
  }, []);

  useEffect(() => {
    if (!isModalOpen) {
      return undefined;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        handleCloseModal();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isModalOpen]);

  const stats = useMemo(() => {
    const active = faqs.filter((faq) => faq.is_active).length;
    const variants = faqs.reduce((sum, faq) => sum + faq.variants.length, 0);
    return {
      total: faqs.length,
      active,
      inactive: faqs.length - active,
      variants
    };
  }, [faqs]);

  const openCreateModal = () => {
    setError(null);
    setEditingFaqId(null);
    setForm(emptyForm);
    setIsModalOpen(true);
  };

  const openEditModal = (faq: FAQItem) => {
    setError(null);
    setEditingFaqId(faq.id);
    setForm({
      canonical_question: faq.canonical_question,
      answer: faq.answer,
      variants_text: faq.variants.join("\n"),
      is_active: faq.is_active
    });
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setEditingFaqId(null);
    setForm(emptyForm);
    setIsModalOpen(false);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    startTransition(async () => {
      try {
        const payload = {
          canonical_question: form.canonical_question,
          answer: form.answer,
          variants: form.variants_text
            .split("\n")
            .map((item) => item.trim())
            .filter(Boolean),
          is_active: form.is_active
        };
        if (editingFaqId === null) {
          await createFaq(payload);
        } else {
          await updateFaq(editingFaqId, payload);
        }

        await loadFaqs();
        handleCloseModal();
      } catch (submitError) {
        const detail =
          submitError instanceof Error
            ? submitError.message
            : "Не удалось сохранить FAQ.";
        setError(detail);
      }
    });
  };

  const handleDelete = (faqId: number) => {
    const confirmed = window.confirm("Удалить запись FAQ?");
    if (!confirmed) {
      return;
    }

    setError(null);

    startTransition(async () => {
      try {
        await deleteFaq(faqId);
        await loadFaqs();
      } catch (deleteError) {
        const detail =
          deleteError instanceof Error
            ? deleteError.message
            : "Не удалось удалить FAQ.";
        setError(detail);
      }
    });
  };

  return (
    <AdminShell
      activeSection="faqs"
      description="Внутренняя панель управления базой знаний для semantic search."
      title="FAQ Management"
    >
      <section className="adminToolbar">
        <div className="statsRow">
          <div className="metricCard">
            <span>Всего FAQ</span>
            <strong>{stats.total}</strong>
          </div>
          <div className="metricCard">
            <span>Активные</span>
            <strong>{stats.active}</strong>
          </div>
          <div className="metricCard">
            <span>Отключённые</span>
            <strong>{stats.inactive}</strong>
          </div>
          <div className="metricCard">
            <span>FAQ variants</span>
            <strong>{stats.variants}</strong>
          </div>
        </div>
        <button className="primaryButton" onClick={openCreateModal} type="button">
          Добавить FAQ
        </button>
      </section>

      {error && !isModalOpen ? <div className="errorBanner">{error}</div> : null}

      <section className="surfaceCard tableCard">
        <div className="panelHeading">
          <div>
            <span className="sectionTag">Knowledge Base</span>
            <h2>FAQ-записи</h2>
          </div>
        </div>

        <div className="tableWrap">
          <table className="dataTable">
            <thead>
              <tr>
                <th>ID</th>
                <th>Канонический вопрос</th>
                <th>Варианты</th>
                <th>Ответ</th>
                <th>Статус</th>
                <th>Updated</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {faqs.length === 0 ? (
                <tr>
                  <td className="emptyTable" colSpan={7}>
                    FAQ пока пуст. Добавьте первую запись через кнопку сверху.
                  </td>
                </tr>
              ) : (
                faqs.map((faq) => (
                  <tr key={faq.id}>
                    <td>{faq.id}</td>
                    <td className="primaryCell">{faq.canonical_question}</td>
                    <td>
                      <div className="previewCell">{trimPreview(faq.variants.join(" • "))}</div>
                    </td>
                    <td>
                      <div className="previewCell">{trimPreview(faq.answer)}</div>
                    </td>
                    <td>
                      <span
                        className={`tableBadge ${faq.is_active ? "success" : "neutral"}`}
                      >
                        {faq.is_active ? "Активна" : "Отключена"}
                      </span>
                    </td>
                    <td>{formatDateTime(faq.updated_at ?? faq.created_at)}</td>
                    <td>
                      <div className="tableActions">
                        <button
                          className="tableButton"
                          onClick={() => openEditModal(faq)}
                          type="button"
                        >
                          Редактировать
                        </button>
                        <button
                          className="tableButton danger"
                          onClick={() => handleDelete(faq.id)}
                          type="button"
                        >
                          Удалить
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {isModalOpen ? (
        <div
          className="modalBackdrop"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              handleCloseModal();
            }
          }}
        >
          <div
            aria-labelledby="faq-modal-title"
            aria-modal="true"
            className="modalCard"
            role="dialog"
          >
            <div className="modalHeader">
              <div>
                <span className="sectionTag">
                  {editingFaqId === null ? "Новая запись" : `FAQ #${editingFaqId}`}
                </span>
                <h2 id="faq-modal-title">
                  {editingFaqId === null ? "Добавить FAQ" : "Редактировать FAQ"}
                </h2>
              </div>
              <button
                aria-label="Закрыть"
                className="iconButton"
                onClick={handleCloseModal}
                type="button"
              >
                ×
              </button>
            </div>

            {error ? <div className="errorBanner">{error}</div> : null}

            <form className="modalForm" onSubmit={handleSubmit}>
              <label className="fieldLabel" htmlFor="faq-question">
                Канонический вопрос
              </label>
              <input
                id="faq-question"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    canonical_question: event.target.value
                  }))
                }
                placeholder="Главная формулировка FAQ"
                value={form.canonical_question}
              />

              <label className="fieldLabel" htmlFor="faq-answer">
                Ответ
              </label>
              <textarea
                id="faq-answer"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    answer: event.target.value
                  }))
                }
                placeholder="Готовый ответ"
                rows={7}
                value={form.answer}
              />

              <label className="fieldLabel" htmlFor="faq-variants">
                Варианты вопроса
              </label>
              <p className="helperText">
                Делайте retrieval-first набор: 10-20 user-like формулировок, включая
                короткие запросы, сокращения, разговорные варианты и частые опечатки.
              </p>
              <textarea
                id="faq-variants"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    variants_text: event.target.value
                  }))
                }
                placeholder={
                  "Одна формулировка на строку\nУ меня пропал домашний интернет\nинет дома не работает\nличная кабина не открывается"
                }
                rows={6}
                value={form.variants_text}
              />

              <label className="checkboxRow">
                <input
                  checked={form.is_active}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      is_active: event.target.checked
                    }))
                  }
                  type="checkbox"
                />
                Использовать запись в semantic search
              </label>

              <div className="modalActions">
                <button className="secondaryButton" onClick={handleCloseModal} type="button">
                  Отменить
                </button>
                <button className="primaryButton" disabled={isPending} type="submit">
                  {isPending
                    ? "Сохраняем..."
                    : editingFaqId === null
                      ? "Добавить FAQ"
                      : "Сохранить изменения"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </AdminShell>
  );
}
