// src/useWsTopics.js
import { useEffect, useRef, useState } from "react";

const WS_URL = import.meta.env.VITE_WS_URL; // z.B. wss://10.253.143.247:3001/ws

export function useWsTopics() {
  const [topics, setTopics] = useState(null);        // {version, topics:[...]}
  const [status, setStatus] = useState("idle");  // idle|connecting|open|error
  const [error, setError] = useState(null);

  const wsRef = useRef(null);

  useEffect(() => {
    if (!WS_URL) {
      setStatus("error");
      setError(new Error("VITE_WS_URL is not set"));
      return;
    }

    function connect() {
      setStatus("connecting");
      setError(null);

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      

      ws.onopen = () => {
        setStatus("open");


        ws.send(JSON.stringify({ "type": "register_client", client_type: "site" }));

      };

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);

          console.log("msg", msg);

          if (msg.type === "connected") {
            setStatus("connected");
          } else if (msg.type === "data") {
            setTopics(msg.data.topics);
            console.log("topics", msg.data.topics);
          }
          // Optional: weitere message types hier behandeln
        } catch (e) {
          console.warn("WS parse error:", e);
        }
      };

      ws.onerror = () => {
        setStatus("error");
        setError(new Error("WebSocket error"));
      };

      ws.onclose = () => {

        setTimeout(connect, 1000);
      };
    }

    connect();

    return () => {
      try { wsRef.current?.close(); } catch {}
    };
  }, []);

  return { topics, status, error };
}
