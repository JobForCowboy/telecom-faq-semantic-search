"use client";

import { FormEvent, useEffect, useState, useTransition } from "react";
import {
  EscalationItem,
  FAQItem,
  createFaq,
  deleteFaq,
  fetchEscalations,
  fetchFaqs,
  updateFaq
} from "@/lib/api";

const emptyForm = {
  question: "",
  answer: "",
  is_active: true
};

export function AdminDashboard() {
  const [faqs, setFaqs] = useState<FAQItem[]>([]);
  const [escalations, setEscalations] = useState<EscalationItem[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editingFaqId, setEditingFaqId] = useState<number | null>(null);
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    const [faqRows, escalationRows] = await Promise.all([
      fetchFaqs(),
      fetchEscalations()
    ]);
    setFaqs(faqRows);
    setEscalations(escalationRows);
  };

  useEffect(() => {
    loadData().catch((loadError) => {
      const detail =
        loadError instanceof Error
          ? loadError.message
          : "Не удалось загрузить данные админки.";
      setError(detail);
    });
  }, []);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    startTransition(async () => {
      try {
        if (editingFaqId === null) {
          await createFaq(form);
        } else {
          await updateFaq(editingFaqId, form);
        }
        setForm(emptyForm);
        setEditingFaqId(null);
        await loadData();
      } catch (submitError) {
        const detail =
          submitError instanceof Error
            ? submitError.message
            : "Не удалось создать FAQ.";
        setError(detail);
      }
    });
  };

  const handleDelete = (faqId: number) => {
    startTransition(async () => {
      try {
        await deleteFaq(faqId);
        await loadData();
      } catch (deleteError) {
        const detail =
          deleteError instanceof Error
            ? deleteError.message
            : "Не удалось удалить FAQ.";
        setError(detail);
      }
    });
  };

  const handleEdit = (faq: FAQItem) => {
    setEditingFaqId(faq.id);
    setForm({
      question: faq.question,
      answer: faq.answer,
      is_active: faq.is_active
    });
  };

  const handleCancelEdit = () => {
    setEditingFaqId(null);
    setForm(emptyForm);
  };

  return (
    <main className="pageShell adminShell">
      <section className="heroPanel compact">
        <div className="badge">Local Admin</div>
        <h1>Управление FAQ и эскалациями</h1>
        <p>
          Локальная панель для CRUD-операций по базе знаний и просмотра вопросов,
          для которых semantic search не нашёл надёжного ответа.
        </p>
        <a className="adminLink" href="/">
          Вернуться в чат
        </a>
      </section>

      <section className="adminGrid">
        <section className="cardPanel">
          <div className="sectionHeading">
            <span className="eyebrow">FAQ</span>
            <h2>Новая запись</h2>
          </div>
          <form className="faqForm" onSubmit={handleSubmit}>
            <input
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  question: event.target.value
                }))
              }
              placeholder="Вопрос из базы знаний"
              value={form.question}
            />
            <textarea
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  answer: event.target.value
                }))
              }
              placeholder="Готовый ответ"
              rows={5}
              value={form.answer}
            />
            <label className="toggleRow">
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
              Активна для поиска
            </label>
            <button disabled={isPending} type="submit">
              {isPending
                ? "Сохраняем..."
                : editingFaqId === null
                  ? "Добавить FAQ"
                  : "Сохранить изменения"}
            </button>
            {editingFaqId !== null ? (
              <button
                className="secondaryButton"
                onClick={handleCancelEdit}
                type="button"
              >
                Отменить редактирование
              </button>
            ) : null}
          </form>
          {error ? <div className="errorBanner">{error}</div> : null}
        </section>

        <section className="cardPanel">
          <div className="sectionHeading">
            <span className="eyebrow">Knowledge Base</span>
            <h2>Текущие FAQ</h2>
          </div>
          <div className="stackList">
            {faqs.map((faq) => (
              <article className="listCard" key={faq.id}>
                <div>
                  <strong>{faq.question}</strong>
                  <p>{faq.answer}</p>
                </div>
                <div className="cardActions">
                  <span>{faq.is_active ? "Активна" : "Отключена"}</span>
                  <div className="inlineActions">
                    <button onClick={() => handleEdit(faq)} type="button">
                      Изменить
                    </button>
                    <button onClick={() => handleDelete(faq.id)} type="button">
                      Удалить
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="cardPanel">
          <div className="sectionHeading">
            <span className="eyebrow">Fallback</span>
            <h2>Эскалированные запросы</h2>
          </div>
          <div className="stackList">
            {escalations.length === 0 ? (
              <div className="listCard">
                <p>Пока нет вопросов, которые ушли на ручную обработку.</p>
              </div>
            ) : (
              escalations.map((item) => (
                <article className="listCard" key={item.id}>
                  <strong>{item.question_text}</strong>
                  <p>{item.response_text}</p>
                  <span>
                    Score:{" "}
                    {item.similarity_score === null
                      ? "n/a"
                      : item.similarity_score.toFixed(3)}
                  </span>
                </article>
              ))
            )}
          </div>
        </section>
      </section>
    </main>
  );
}
