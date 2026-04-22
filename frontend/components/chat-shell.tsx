"use client";

import { FormEvent, useMemo, useState, useTransition } from "react";
import { ChatResponse, queryChat } from "@/lib/api";

const starterPrompts = [
  "инет дома не работает",
  "не могу зайти в лк",
  "как оплатить связь",
  "мобила плохо ловит"
];

function formatSimilarity(score: number | null) {
  if (score === null) {
    return "n/a";
  }

  return `${Math.round(score * 100)}%`;
}

export function ChatShell() {
  const [question, setQuestion] = useState("");
  const [latestQuestion, setLatestQuestion] = useState<string | null>(null);
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const canSubmit = question.trim().length >= 3 && !isPending;
  const suggestionChips = useMemo(
    () =>
      starterPrompts.map((prompt) => (
        <button
          className="suggestionChip"
          key={prompt}
          onClick={() => setQuestion(prompt)}
          type="button"
        >
          {prompt}
        </button>
      )),
    []
  );

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) {
      return;
    }

    setError(null);
    setLatestQuestion(trimmed);

    startTransition(async () => {
      try {
        const response = await queryChat(trimmed);
        setResult(response);
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
    <main className="appShell">
      <header className="topBar">
        <div>
          <span className="sectionTag">Telecom Support</span>
          <h1 className="pageTitle">FAQ Semantic Search</h1>
        </div>
        <div className="statusBadge">Support tool MVP</div>
      </header>

      <section className="pageIntro">
        <p>
          Задайте вопрос по тарифам, оплате, качеству связи или домашнему
          интернету. Сервис ищет по FAQ variants, нормализует сокращения и
          разговорные формы, а затем возвращает готовый ответ или отправляет
          запрос на ручную обработку.
        </p>
      </section>

      <div className="workspaceGrid">
        <section className="surfaceCard inputCard">
          <div className="panelHeading">
            <div>
              <span className="sectionTag">Запрос</span>
              <h2>Что нужно пользователю?</h2>
            </div>
          </div>

          <form className="queryForm" onSubmit={handleSubmit}>
            <label className="fieldLabel" htmlFor="support-question">
              Вопрос
            </label>
            <textarea
              id="support-question"
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Например: У меня пропал домашний интернет"
              rows={4}
              value={question}
            />
            <div className="formFooter">
              <span className="helperText">
                Минимум 3 символа. Поддерживаются короткие запросы вроде `лк`,
                `инет` и разговорные формулировки.
              </span>
              <button className="primaryButton" disabled={!canSubmit} type="submit">
                {isPending ? "Идёт поиск..." : "Найти ответ"}
              </button>
            </div>
          </form>

          <div className="suggestionRow">
            <span className="sectionTag muted">Примеры</span>
            <div className="chipWrap">{suggestionChips}</div>
          </div>
        </section>

        <section className="surfaceCard resultCard">
          <div className="panelHeading">
            <div>
              <span className="sectionTag">Результат</span>
              <h2>Ответ системы</h2>
            </div>
            {result ? (
              <span
                className={`statusBadge ${result.status === "matched" ? "success" : "warning"}`}
              >
                {result.status === "matched" ? "Найден FAQ" : "Нужна эскалация"}
              </span>
            ) : null}
          </div>

          {error ? <div className="errorBanner">{error}</div> : null}

          {isPending ? (
            <div className="resultState">
              <p className="resultTitle">Ищем подходящий ответ...</p>
              <p>
                Сравниваем вопрос с FAQ-базой и проверяем, проходит ли найденное
                совпадение по порогу уверенности.
              </p>
            </div>
          ) : result ? (
            <div className="resultState">
              {latestQuestion ? (
                <div className="contextBlock">
                  <span className="sectionTag muted">Последний запрос</span>
                  <p>{latestQuestion}</p>
                </div>
              ) : null}

              <div className="resultBody">
                <p className="resultTitle">{result.answer}</p>
              </div>

              <div className="metaGrid">
                <div className="metaItem">
                  <span>Статус</span>
                  <strong>
                    {result.status === "matched"
                      ? "Готовый ответ из базы"
                      : "Эскалация после слабого матча"}
                  </strong>
                </div>
                <div className="metaItem">
                  <span>Уверенность</span>
                  <strong>{formatSimilarity(result.score)}</strong>
                </div>
                <div className="metaItem wide">
                  <span>Найденная формулировка</span>
                  <strong>{result.matched_question ?? "Совпадение не прошло по порогу"}</strong>
                </div>
                <div className="metaItem wide">
                  <span>Что произошло</span>
                  <strong>
                    {result.status === "matched"
                      ? "Backend нашёл достаточное semantic совпадение и вернул канонический FAQ-ответ."
                      : "Лучший кандидат оказался ниже порога, поэтому запрос ушёл в fallback и очередь эскалации."}
                  </strong>
                </div>
              </div>
            </div>
          ) : (
            <div className="resultState empty">
              <p className="resultTitle">Пока нет результата</p>
              <p>
                После отправки вопроса здесь появится найденный FAQ-ответ или
                fallback-сообщение с признаком эскалации.
              </p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
