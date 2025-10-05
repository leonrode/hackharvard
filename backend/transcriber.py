import time
import threading
import logging
from typing import Generator, Optional, Callable, Dict
from dataclasses import dataclass
from google.cloud import speech_v1 as speech
from audio_streams import AudioStream
from chunking import chunk_transcript_by_topics
from topic_manager import TopicManager

import dotenv

dotenv.load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class TranscriberConfig:
    language_code: str = "en-US"
    sample_rate_hertz: int = 16000
    encoding: speech.RecognitionConfig.AudioEncoding = (
        speech.RecognitionConfig.AudioEncoding.LINEAR16
    )
    min_word_count: int = 10
    min_time_since_dump: float = 5.0
    enable_automatic_punctuation: bool = True
    model: str = "default"
    vertex_project_id: Optional[str] = None
    vertex_location: str = "us-central1"
    restart_interval_seconds: float = 300.0


class Transcriber:
    def __init__(
        self,
        topic_manager: TopicManager,
        config: Optional[TranscriberConfig] = None,
        on_working_buffer_update: Optional[Callable[[str], None]] = None,
        on_dump: Optional[Callable[[str], None]] = None,
        on_chunks_produced: Optional[Callable[[Dict[str, str]], None]] = None,
        previous_recommendations: Optional[Dict[str, str]] = None,
    ):
        self.topic_manager = topic_manager
        self.config = config or TranscriberConfig()
        self.on_working_buffer_update = on_working_buffer_update
        self.on_dump = on_dump
        self.on_chunks_produced = on_chunks_produced
        self.previous_recommendations = previous_recommendations
        self.working_buffer: str = ""
        self.long_term_buffer: str = ""

        self._last_interim_text: str = ""
        self._last_dump_time: float = time.time()
        self._stream_start_time: float = time.time()
        self._is_running = False
        self._needs_restart = False
        self._transcription_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self.client = speech.SpeechClient()

    def dump_ready(self) -> bool:
        with self._lock:
            if not self.working_buffer:
                return False

            word_count = len(self.working_buffer.split())
            time_since_dump = time.time() - self._last_dump_time

            return (
                word_count >= self.config.min_word_count
                and time_since_dump >= self.config.min_time_since_dump
            )

    def _should_restart_stream(self) -> bool:
        if self.config.restart_interval_seconds <= 0:
            return False

        time_since_start = time.time() - self._stream_start_time
        return time_since_start >= self.config.restart_interval_seconds

    def _dump_to_long_term(self) -> None:
        with self._lock:
            if not self.working_buffer:
                return

            text_to_chunk = self.working_buffer
            dumped_text = self.working_buffer

        logger.info("Dumping working buffer to long-term")
        logger.debug(f"Text to chunk: {text_to_chunk[:100]}...")
        logger.debug(f"Word count: {len(text_to_chunk.split())}")

        try:
            existing_topics = self.topic_manager.get_topic_summaries_formatted()
            logger.debug(f"Existing topics:\n{existing_topics}")

            result = chunk_transcript_by_topics(
                text_to_chunk,
                existing_topics=existing_topics,
                project_id=self.config.vertex_project_id,
                location=self.config.vertex_location,
                previous_recommendations=self.previous_recommendations,
            )

            logger.debug(f"Chunking result: {result}")

            complete_chunks = result.get("complete_chunks", {})
            chunk_blurbs = result.get("chunk_blurbs", {})
            incomplete_text = result.get("incomplete_text", "")
            topic_descriptions = result.get("topic_descriptions", {})

            logger.info(f"Complete chunks: {list(complete_chunks.keys())}")
            logger.debug(f"Incomplete text length: {len(incomplete_text)}")
            logger.debug(f"Topic descriptions: {list(topic_descriptions.keys())}")

            with self._lock:
                if complete_chunks:
                    for topic_id, contents in complete_chunks.items():
                        blurbs = chunk_blurbs.get(topic_id, [])
                        description = topic_descriptions.get(topic_id, "")

                        for content, blurb in zip(contents, blurbs):
                            self.topic_manager.add_chunk(
                                topic_id=topic_id,
                                chunk_content=content,
                                chunk_blurb=blurb,
                                topic_description=description,
                            )
                            logger.info(
                                f"Added chunk to topic: {topic_id} with blurb: '{blurb}'"
                            )

                        if description:
                            logger.info(f"Updated description for topic {topic_id}")

                    if self.on_chunks_produced:
                        self.on_chunks_produced(complete_chunks)

                if self.long_term_buffer and incomplete_text:
                    self.long_term_buffer += " " + incomplete_text
                elif incomplete_text:
                    self.long_term_buffer = incomplete_text

                self.working_buffer = ""
                self._last_interim_text = ""
                self._last_dump_time = time.time()

            if self.on_dump:
                self.on_dump(dumped_text)

        except Exception as e:
            logger.error(f"Error chunking transcript: {e}", exc_info=True)

            with self._lock:
                if self.long_term_buffer:
                    self.long_term_buffer += " " + self.working_buffer
                else:
                    self.long_term_buffer = self.working_buffer

                self.working_buffer = ""
                self._last_interim_text = ""
                self._last_dump_time = time.time()

            if self.on_dump:
                self.on_dump(dumped_text)

    def _create_streaming_config(self) -> speech.StreamingRecognitionConfig:
        recognition_config = speech.RecognitionConfig(
            encoding=self.config.encoding,
            sample_rate_hertz=self.config.sample_rate_hertz,
            language_code=self.config.language_code,
            enable_automatic_punctuation=self.config.enable_automatic_punctuation,
            model=self.config.model,
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=recognition_config, interim_results=True
        )
        return streaming_config

    def _audio_generator(
        self,
    ) -> Generator[speech.StreamingRecognizeRequest, None, None]:
        """for audio_chunk in self.audio_stream.get_chunk_generator():
            print(f"Audio chunk: {audio_chunk}")
            if not self._is_running:
                break
            if not isinstance(audio_chunk, bytes):
                raise TypeError(f"Audio chunk must be bytes, got {type(audio_chunk)}")
            if len(audio_chunk) == 0:
                continue
            yield speech.StreamingRecognizeRequest(audio_content=audio_chunk)"""

    def _process_responses(
        self, responses: Generator[speech.StreamingRecognizeResponse, None, None]
    ) -> None:
        for response in responses:

            if not response.results:
                continue

            result = response.results[0]

            if not result.alternatives:
                continue

            transcript = result.alternatives[0].transcript
            is_final = result.is_final

            with self._lock:
                if is_final:
                    if self.working_buffer and self._last_interim_text:
                        final_text = self.working_buffer[
                            : -len(self._last_interim_text)
                        ]
                        if final_text:
                            self.working_buffer = final_text + " " + transcript
                        else:
                            self.working_buffer = transcript
                    else:
                        if self.working_buffer:
                            self.working_buffer += " " + transcript
                        else:
                            self.working_buffer = transcript
                    self._last_interim_text = ""
                else:
                    if self._last_interim_text:
                        base_text = self.working_buffer[: -len(self._last_interim_text)]
                    else:
                        base_text = self.working_buffer

                    if base_text and transcript:
                        self.working_buffer = base_text + " " + transcript
                    elif transcript:
                        self.working_buffer = transcript
                    else:
                        self.working_buffer = base_text

                    self._last_interim_text = (
                        " " + transcript if base_text and transcript else transcript
                    )

                if self.on_working_buffer_update:
                    self.on_working_buffer_update(self.working_buffer)

            if is_final and self.dump_ready():
                self._dump_to_long_term()

    def _transcription_loop(self, audio_element) -> None:

        try:
            self._stream_start_time = time.time()
            self._needs_restart = False

            logger.info(
                f"Starting transcription stream (restart interval: {self.config.restart_interval_seconds}s)"
            )

            streaming_config = self._create_streaming_config()

            responses = self.client.streaming_recognize(
                config=streaming_config, requests=[speech.StreamingRecognizeRequest(audio_content=audio_element)]
            )
            self._process_responses(responses)

            if self._needs_restart and self._is_running:
                logger.info("Performing stream restart: dumping working buffer")
                if self.working_buffer:
                    self._dump_to_long_term()
                logger.info("Stream restart complete, restarting recognition")


        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            if self._is_running:
                logger.warning("Error in transcription, restarting in 2 seconds...")
                time.sleep(2)


    def start(self) -> None:
        if self._is_running:
            return

        self._is_running = True
        self.audio_stream.start()

        self._transcription_thread = threading.Thread(
            target=self._transcription_loop, daemon=True
        )
        self._transcription_thread.start()
        logger.info("Transcription thread started")

    def stop(self) -> None:
        if not self._is_running:
            return

        self._is_running = False
        self.audio_stream.stop()

        if self._transcription_thread:
            self._transcription_thread.join(timeout=5.0)
            self._transcription_thread = None

        if self.working_buffer:
            self._dump_to_long_term()

        logger.info("Transcription stopped")

    def get_working_buffer_text(self) -> str:
        with self._lock:
            return self.working_buffer

    def get_long_term_buffer_text(self) -> str:
        with self._lock:
            return self.long_term_buffer

    def get_full_transcript(self) -> str:
        with self._lock:
            if self.long_term_buffer and self.working_buffer:
                return self.long_term_buffer + " " + self.working_buffer
            elif self.long_term_buffer:
                return self.long_term_buffer
            else:
                return self.working_buffer

    def clear_buffers(self) -> None:
        with self._lock:
            self.working_buffer = ""
            self.long_term_buffer = ""
            self._last_interim_text = ""
            self._last_dump_time = time.time()
            self._stream_start_time = time.time()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
