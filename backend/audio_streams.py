from abc import ABC, abstractmethod
from typing import Generator
import json
import base64
import asyncio
import queue
import threading


class AudioStream(ABC):
    @abstractmethod
    def get_chunk_generator(self) -> Generator[bytes, None, None]:
        pass

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def is_active(self) -> bool:
        pass


class WebSocketAudioStream(AudioStream):
    def __init__(self, websocket):
        self.websocket = websocket
        self._queue = queue.Queue(maxsize=100)
        self._running = False
        self._thread = None
        self._loop = None

    async def _consume_websocket(self):
        try:
            async for message in self.websocket:
                if not self._running:
                    break

                data = json.loads(message)
                audio_data = data.get("data")

                if isinstance(audio_data, list):
                    try:
                        audio_buffer = bytes(audio_data)
                        self._queue.put(audio_buffer)
                    except (ValueError, OverflowError) as e:
                        print(f"Invalid audio data values: {str(e)}")
                        continue

                elif isinstance(audio_data, str):
                    try:
                        audio_buffer = base64.b64decode(audio_data)
                        self._queue.put(audio_buffer)
                    except Exception as e:
                        print(f"Invalid base64 data: {str(e)}")
                        continue
                else:
                    print(f"Unexpected data type: {type(audio_data)}")
                    continue
        except Exception as e:
            print(f"Error in websocket consumer: {e}")
        finally:
            self._queue.put(None)

    def _run_async_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._consume_websocket())

    def get_chunk_generator(self) -> Generator[bytes, None, None]:
        while self._running or not self._queue.empty():
            try:
                chunk = self._queue.get(timeout=0.1)
                if chunk is None:
                    break
                yield chunk
            except queue.Empty:
                continue

    def start(self, websocket=None) -> None:
        if websocket:
            self.websocket = websocket

        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.websocket = None

    def is_active(self) -> bool:
        return self._running and self.websocket is not None
