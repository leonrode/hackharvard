import "./App.css";
import { useWsTopics } from "./useWsTopics";
import { useState, useEffect, useRef } from "react";
import { motion, useScroll } from "framer-motion";



export default function App() {
  let { topics, status } = useWsTopics();

  const [allTopics, setAllTopics] = useState([]);
  const [expandedItems, setExpandedItems] = useState(new Set());
  const [scrollPosition, setScrollPosition] = useState(0);
  const scrollRef = useRef(null);
  const { scrollX } = useScroll({ container: scrollRef });

  // Update scroll position for calculations
  useEffect(() => {
    const unsubscribe = scrollX.onChange(setScrollPosition);
    return unsubscribe;
  }, [scrollX]);

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

  const toggleExpanded = (topicKey, itemIndex) => {
    const itemId = `${topicKey}-${itemIndex}`;
    setExpandedItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(itemId)) {
        newSet.delete(itemId);
      } else {
        newSet.add(itemId);
      }
      return newSet;
    });
  };



  return (
    <div className="wrapper">
      <header className="header">
        <h1 className="brand">echopilot</h1>
        <h2 className="subtitle">
          {status}
        </h2>
      </header>

      <section className="hstrip" aria-label="Topics carousel" ref={scrollRef}>
        {allTopics.map((t, index) => {
          // Calculate staggered effects based on scroll position and index
          const waveOffset = index * 0.5;
          const yOffset = Math.sin((scrollPosition / 200) + waveOffset) * (10 + index * 2);
          const scaleValue = 1 + Math.sin((scrollPosition / 300) + waveOffset) * (0.02 + index * 0.005);
          const rotateValue = Math.sin((scrollPosition / 400) + waveOffset) * (1 + index * 0.3);
          const opacityValue = 0.9 + Math.sin((scrollPosition / 500) + waveOffset) * (0.1 + index * 0.02);
          
          return (
            <motion.article 
              className="topic" 
              key={t.topic_key}
              style={{

              }}
              transition={{
                type: "spring",
                stiffness: 100,
                damping: 20,
                delay: index * 0.1, // Stagger the initial animation
              }}
            >
            <input className="topic__title" defaultValue={t.topic_key.replaceAll("-", " ")} aria-label={`${t.topic_key} title`} />
            <div className="topic__box" role="region" aria-label={`${t.topic_key} list`}>
              <div className="topic__list">
                {(t.content_stack ?? []).map((it, index) => {
                  const itemId = `${t.topic_key}-${index}`;
                  const isExpanded = expandedItems.has(itemId);
                  
                  return (
                    <div 
                      key={index} 
                      className={`topic__item ${isExpanded ? 'expanded' : ''}`}
                      onClick={() => toggleExpanded(t.topic_key, index)}
                      style={{ cursor: 'pointer' }}
                    >
                      <span className="topic__blurb">
                        {it.blurb}
                      </span>

                      {isExpanded && (
                        <span className="topic__content">
                          {it.content}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
              <div className="arrow__div">
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
            </motion.article>
          );
        })}

        {allTopics.length === 0 && (
          <div style={{ alignSelf: "center", opacity: 0.6 }}>No topics received yet…</div>
        )}
      </section>
    </div>
  );
}
