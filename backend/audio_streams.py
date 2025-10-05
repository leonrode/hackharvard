from abc import ABC, abstractmethod
from typing import Generator, Optional
import json
import base64
import time



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


    async def get_chunk_generator(self) -> Generator[bytes, None, None]:

        async for message in self.websocket:
            data = json.loads(message)
            audio_data = data.get('data')
            
            if isinstance(audio_data, list):
                # Data is a list of integers (raw audio bytes)
                try:
                    audio_buffer = bytes(audio_data)
                    yield audio_buffer

                except (ValueError, OverflowError) as e:
                    self.send_error(self.websocket, f'Invalid audio data values: {str(e)}')
                    yield None

            elif isinstance(audio_data, str):
                # Data is a base64 encoded string
                try:
                    audio_buffer = base64.b64decode(audio_data)
                    yield audio_buffer
                except Exception as e:

                    self.send_error(self.websocket, f'Invalid base64 data: {str(e)}')
                    yield None

        else:
            print(f"Unexpected data type: {type(audio_data)}")
            self.send_error(self.websocket, 'Invalid audio data format')
            yield None

    def start(self, websocket=None) -> None:
        if websocket:
            self.websocket = websocket

    def stop(self) -> None:
        self.websocket = None

    def is_active(self) -> bool:
        return self.websocket is not None