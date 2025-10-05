import "./App.css";
import { useWsTopics } from "./useWsTopics";
import { useState, useEffect } from "react";

const fixedSuggestions = [
  "Got it, could you elaborate?",
  "What’s the next step?",
  "Can you share an example?"
];

export default function App() {
  let { topics, status } = useWsTopics();


  const [allTopics, setAllTopics] = useState([]);

  useEffect(() => {

    if (!topics) return;
    topics.forEach(new_t => {
      if (!allTopics.map(t => t.topic_key).includes(new_t.topic_key)) {
        setAllTopics([...allTopics, new_t]);
      } else {
        setAllTopics(allTopics.map(t => t.topic_key === new_t.topic_key ? new_t : t));
      }
    })
  }, [topics])



  return (
    <div className="wrapper">
      <header className="header">
        <h1 className="brand">EchoPilot</h1>
        <h2 className="subtitle">
          {status}
        </h2>
      </header>

      <section className="hstrip" aria-label="Topics carousel">
        {allTopics.map((t) => (
          <article className="topic" key={t.topic_key}>
            <input className="topic__title" defaultValue={t.topic_key} aria-label={`${t.topic_key} title`} />
            <div className="topic__box" role="region" aria-label={`${t.topic_key} list`}>
              <ul className="topic__list">
                {(t.content_stack ?? []).map((it) => (
                  <li key={it} className="topic__item">{it.blurb ?? it.content ?? it.toString()}</li>
                ))}
              </ul>
              <div className="">
                <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="currentColor" class="bi bi-arrow-up-short" viewBox="0 0 16 16">
                  <path fill-rule="evenodd" d="M8 12a.5.5 0 0 0 .5-.5V5.707l2.146 2.147a.5.5 0 0 0 .708-.708l-3-3a.5.5 0 0 0-.708 0l-3 3a.5.5 0 1 0 .708.708L7.5 5.707V11.5a.5.5 0 0 0 .5.5"/>
                </svg>
              </div>
            </div>

            <div className="suggestions" aria-label="Fixed suggestions">
              {t.recommendations.map((r) => (
                <div key={r} className="sg">{r}</div>
              ))}
            </div>
          </article>
        ))}

        {allTopics.length === 0 && (
          <div style={{ alignSelf: "center", opacity: 0.6 }}>No topics received yet…</div>
        )}
      </section>
    </div>
  );
}
