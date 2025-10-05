import "./App.css";
import { useWsTopics } from "./useWsTopics";

const fixedSuggestions = [
  "Got it, could you elaborate?",
  "What’s the next step?",
  "Can you share an example?"
];

export default function App() {
  let { topics, status } = useWsTopics();

  topics = topics ?? [];



  return (
    <div className="wrapper">
      <header className="header">
        <h1 className="brand">EchoPilot</h1>
        <h2 className="subtitle">
          {status}
        </h2>
      </header>

      <section className="hstrip" aria-label="Topics carousel">
        {topics.map((t) => (
          <article className="topic" key={t.id}>
            <input className="topic__title" defaultValue={t.topic_key} aria-label={`${t.topic_key} title`} />
            <div className="topic__box" role="region" aria-label={`${t.topic_key} list`}>
              <ul className="topic__list">
                {(t.content_stack ?? []).map((it) => (
                  <li key={it} className="topic__item">{it}</li>
                ))}
              </ul>
            </div>
            <div className="suggestions" aria-label="Fixed suggestions">
              {t.recommendations.map((r) => (
                <div key={r.id} className="sg">{r}</div>
              ))}
            </div>
          </article>
        ))}

        {topics.length === 0 && (
          <div style={{ alignSelf: "center", opacity: 0.6 }}>No topics received yet…</div>
        )}
      </section>
    </div>
  );
}
