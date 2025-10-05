from typing import Dict, List, Tuple
from dataclasses import dataclass, field
import threading


@dataclass
class Chunk:
    blurb: str
    content: str


@dataclass
class Topic:
    description: str
    chunk_stack: List[Chunk] = field(default_factory=list)


class TopicManager:
    def __init__(self):
        self._topics: Dict[str, Topic] = {}
        self._lock = threading.Lock()

    def add_chunk(
        self,
        topic_id: str,
        chunk_content: str,
        chunk_blurb: str = "",
        topic_description: str = "",
    ) -> None:
        with self._lock:
            if topic_id not in self._topics:
                self._topics[topic_id] = Topic(description=topic_description)
            chunk = Chunk(blurb=chunk_blurb, content=chunk_content)
            self._topics[topic_id].chunk_stack.append(chunk)

    def update_description(self, topic_id: str, description: str) -> None:
        with self._lock:
            if topic_id not in self._topics:
                self._topics[topic_id] = Topic(description=description)
            else:
                self._topics[topic_id].description = description

    def get_topic_summaries(self) -> Dict[str, str]:
        with self._lock:
            return {
                topic_id: topic.description for topic_id, topic in self._topics.items()
            }

    def get_topic_summaries_formatted(self) -> str:
        with self._lock:
            if not self._topics:
                return "No topics yet."

            formatted = ""
            for topic_id, topic in self._topics.items():
                formatted += f"- {topic_id}: {topic.description}\n"
            return formatted.strip()

    def get_all_topics(self) -> Dict[str, Topic]:
        with self._lock:
            return {topic_id: topic for topic_id, topic in self._topics.items()}

    def get_chunks_for_topic(self, topic_id: str) -> List[Chunk]:
        with self._lock:
            if topic_id in self._topics:
                return list(self._topics[topic_id].chunk_stack)
            return []

    def get_all_chunks(self) -> Dict[str, List[Chunk]]:
        with self._lock:
            return {
                topic_id: list(topic.chunk_stack)
                for topic_id, topic in self._topics.items()
            }

    def clear(self) -> None:
        with self._lock:
            self._topics.clear()
