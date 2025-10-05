import asyncio
import websockets
import json
import os
import time
import queue
import uuid
from datetime import datetime
import sys
import base64
import struct
import signal
import pyaudio

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcriber import Transcriber
from recommender import Recommender
from topic_manager import TopicManager

class WebSocketServer:
    def __init__(self, host='0.0.0.0', port=3001):
        self.host = host
        self.port = port
        self.phone_socket = None
        self.site_socket = None
        
        # Audio processing components
        self.audio_chunks = []
        self.strip_headers = True
        self.raw_file_header_size = 44
        self.audio_queue = queue.Queue()
        
        # Service instances
        self.transcriber = Transcriber()
        self.recommender = Recommender()
        self.topic_manager = TopicManager()
        
        # Server state
        self.server = None
        self.active_connections = set()
        self.shutdown_event = asyncio.Event()
        
        

    def queue_audio_data(self, audio_data):
        """Queue audio data for playback"""
        if not self.audio_queue.full():
            self.audio_queue.put(audio_data)

        print(f"Total audio queue size: {self.audio_queue.qsize()}")
        
        # Process audio directly with transcriber
        self.transcriber.transcribe_audio_queue(self.audio_queue)

    
    

    def strip_audio_header(self, audio_data):
        """Strip common audio file headers from raw audio data"""
        if len(audio_data) < 44:  # Minimum size for any meaningful audio data
            return audio_data
        
        # Check for WAV header (starts with "RIFF")
        if audio_data[:4] == b'RIFF':
            # WAV header is typically 44 bytes, but let's find the actual data start
            # Look for "data" chunk marker
            data_start = audio_data.find(b'data')
            if data_start != -1:
                # Skip "data" marker (4 bytes) and size field (4 bytes)
                return audio_data[data_start + 8:]
            else:
                # Fallback: assume 44-byte header
                return audio_data[44:]
        
        # Check for other common headers
        elif audio_data[:4] == b'OggS':  # OGG header
            # OGG is more complex, for now just skip first 100 bytes as approximation
            return audio_data[100:]
        
        elif audio_data[:3] == b'ID3':  # MP3 with ID3 tag
            # ID3 tag size is in bytes 6-9 (big-endian)
            if len(audio_data) >= 10:
                tag_size = struct.unpack('>I', b'\x00' + audio_data[6:9])[0]
                return audio_data[10 + tag_size:]
            else:
                return audio_data[10:]
        
        # Check for .raw file patterns (common raw audio formats)
        elif self.is_raw_audio_format(audio_data):
            print("Detected raw audio format")
            # Common .raw file headers are often 44 bytes (WAV-like) or 0 bytes
            # Try different header sizes
            for header_size in [44, 16, 8]:
                if len(audio_data) > header_size:
                    test_data = audio_data[header_size:]
                    if self.looks_like_audio_data(test_data):
                        return test_data
            # If no header size works, return as-is
            return audio_data
        
        # Check for raw PCM data patterns
        # If it looks like raw 16-bit PCM (no obvious header), return as-is
        else:
            # Check if the data looks like raw PCM by examining byte patterns
            # Raw PCM typically has more variation in byte values
            sample_bytes = audio_data[:min(1024, len(audio_data))]
            byte_variance = len(set(sample_bytes))
            
            if byte_variance > 50:  # High variance suggests raw audio data
                print("🎵 Detected raw PCM data, no header stripping needed")
                return audio_data
            else:
                print("🎵 Unknown format, attempting to strip first 44 bytes")
                return audio_data[44:]

    def is_raw_audio_format(self, audio_data):
        """Check if this looks like a .raw audio file"""
        if len(audio_data) < 16:
            return False
        
        # .raw files often have specific patterns or are just raw PCM
        # Check for common .raw file characteristics
        return True  # For now, assume it could be .raw if we get here

    def looks_like_audio_data(self, data):
        """Check if data looks like valid audio samples"""
        if len(data) < 100:
            return False
        
        # Check for audio-like characteristics:
        # 1. Reasonable byte variance (not all zeros or all same value)
        # 2. Some structure that suggests audio samples
        sample = data[:min(1000, len(data))]
        unique_bytes = len(set(sample))
        
        # Should have some variation but not be completely random
        return 10 < unique_bytes < 200

    def detect_audio_format(self, audio_data):
        """Detect the audio format from the data"""
        if len(audio_data) < 4:
            return "unknown"
        
        if audio_data[:4] == b'RIFF':
            return "wav"
        elif audio_data[:4] == b'OggS':
            return "ogg"
        elif audio_data[:3] == b'ID3':
            return "mp3"
        elif audio_data[:4] == b'fLaC':
            return "flac"
        else:
            return "raw_pcm"

    async def handle_client(self, websocket, path=None):
        """Handle new WebSocket client connection"""
        client_address = websocket.remote_address
        client_id = str(uuid.uuid4())
        client_type = 'unknown'
        
        # Add to active connections
        self.active_connections.add(websocket)
        
        print(f"New connection attempt from {client_address}")
        print(f"Client ID: {client_id}")
        print(f"Active connections: {len(self.active_connections)}")
        
        try:
            # Send welcome message
            welcome_message = {
                'type': 'welcome',
                'message': 'Connected to real-time recommendations server',
                'client_id': client_id,
                'timestamp': int(time.time() * 1000)
            }
            await websocket.send(json.dumps(welcome_message))
            
            # Handle incoming messages
            try:
                async for message in websocket:
                    try:

                        data = json.loads(message)
                        await self.handle_message(websocket, client_id, data)
                    except json.JSONDecodeError as e:
                        print(f'JSON decode error from {client_id}: {e}')
                        print(f'Raw message: {message}')
                        await self.send_error(websocket, f'Invalid JSON: {str(e)}')
                    except Exception as e:
                        print(f'Error processing message from {client_id}: {e}')
                        print(f'Message type: {type(message)}, Length: {len(message) if message else 0}')
                        await self.send_error(websocket, f'Error processing message: {str(e)}')
            except websockets.exceptions.ConnectionClosedError as e:
                print(f'Connection closed by client {client_id}: {e}')
            except websockets.exceptions.WebSocketException as e:
                print(f'WebSocket error with client {client_id}: {e}')
            except Exception as e:
                print(f'Unexpected error in message loop for client {client_id}: {e}')
                print(f'Error type: {type(e).__name__}')
        
        except websockets.exceptions.ConnectionClosed:
            print(f'Client {client_id} disconnected')
            self.cleanup_client(client_id, websocket)
        except Exception as e:
            print(f'WebSocket error: {e}')
            self.cleanup_client(client_id, websocket)

    def cleanup_client(self, client_id, websocket=None):
        """Clean up client connection"""
        # Remove from active connections
        if websocket and websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"Removed client {client_id} from active connections")
        
        # Clear socket references
        if self.phone_socket and self.phone_socket == client_id:
            self.phone_socket = None
            print("Phone client disconnected")
        elif self.site_socket and self.site_socket == client_id:
            self.site_socket = None
            print("Site client disconnected")
        
        print(f"Active connections remaining: {len(self.active_connections)}")

    async def handle_message(self, websocket, client_id, data):
        """Handle incoming WebSocket messages"""
        message_type = data.get('type')
        
        if message_type == 'register_client':
            await self.handle_register_client(websocket, client_id, data)
        elif message_type == 'audio_chunk':
            await self.handle_audio_chunk(websocket, client_id, data)
        elif message_type == 'get_recommendations':
            await self.handle_get_recommendations(websocket, client_id, data)
        elif message_type == 'clear_audio_chunks':
            await self.handle_clear_audio_chunks(websocket, client_id, data)
        elif message_type == 'toggle_audio_playback':
            await self.handle_toggle_audio_playback(websocket, client_id, data)
        else:
            await self.send_error(websocket, f'Unknown message type: {message_type}')

    async def handle_register_client(self, websocket, client_id, data):
        """Handle client registration"""
        client_type = data.get('client_type', 'unknown')
        print(f"Registering client {client_id} with type {client_type}")
        
        # Check if we can accept this connection

        if client_type == 'site':
            self.site_socket = client_id
            print(f"Site client connected: {self.site_socket}")
            await self.send_message(websocket, {
                'type': 'connected',
                'client_id': self.site_socket,
                'client_type': 'site',
                'message': 'Site client connected successfully'
            })

            await self.send_message(websocket, {
                "type": "data",
                "client_id": self.site_socket,
                "client_type": "site",
                "data": {
                    "topics": [{
                        "topic_key": "topic_key",
                        "topic_summary": "topic_summary",
                        "content_stack": ["content_1", "content_2", "content_3"],
                        "recommendations": ["recommendation_1", "recommendation_2", "recommendation_3"],
                    },{
                        "topic_key": "topic_key",
                        "topic_summary": "topic_summary",
                        "content_stack": ["content_1", "content_2", "content_3"],
                        "recommendations": ["recommendation_1", "recommendation_2", "recommendation_3"],
                    },{
                        "topic_key": "topic_key",
                        "topic_summary": "topic_summary",
                        "content_stack": ["content_1", "content_2", "content_3"],
                        "recommendations": ["recommendation_1", "recommendation_2", "recommendation_3"],
                    },
                    {
                        "topic_key": "topic_key",
                        "topic_summary": "topic_summary",
                        "content_stack": ["content_1", "content_2", "content_3", "content_4", "content_5", "content_6", "content_7", "content_8", "content_9", "content_10","content_11", "content_12", "content_13", "content_14", "content_15", "content_16", "content_17", "content_18", "content_19", "content_20"],
                        "recommendations": ["recommendation_1", "recommendation_2", "recommendation_3"],
                    },
                    {
                        "topic_key": "topic_key",
                        "topic_summary": "topic_summary",
                        "content_stack": ["content_1", "content_2", "content_3"],
                        "recommendations": ["recommendation_1", "recommendation_2", "recommendation_3"],
                    },
                    {
                        "topic_key": "topic_key",
                        "topic_summary": "topic_summary",
                        "content_stack": ["content_1", "content_2", "content_3"],
                        "recommendations": ["recommendation_1", "recommendation_2", "recommendation_3"],
                    },]
                }
            })
        else:
            self.phone_socket = client_id
            print(f"Phone client connected: {self.phone_socket}")
            await self.send_message(websocket, {
                'type': 'connected',
                'client_id': self.phone_socket,
                'client_type': 'phone',
                'message': 'Phone client connected successfully'
            })

    async def handle_audio_chunk(self, websocket, client_id, data):
        """Handle audio data from phone client"""
        # Only phone client should send audio
        if client_id != self.phone_socket:
            await self.send_error(websocket, 'Only phone client can send audio')
            return
        
        try:
            # Convert audio data back to bytes - handle different formats
            audio_data = data.get('data')
            
            if isinstance(audio_data, list):
                # Data is a list of integers (raw audio bytes)
                try:
                    audio_buffer = bytes(audio_data)

                except (ValueError, OverflowError) as e:

                    await self.send_error(websocket, f'Invalid audio data values: {str(e)}')
                    return

            elif isinstance(audio_data, str):
                # Data is a base64 encoded string
                try:
                    audio_buffer = base64.b64decode(audio_data)

                except Exception as e:

                    await self.send_error(websocket, f'Invalid base64 data: {str(e)}')
                    return


            else:
                print(f"Unexpected data type: {type(audio_data)}")
                await self.send_error(websocket, 'Invalid audio data format')
                return



            self.queue_audio_data(audio_buffer)

            # Detect audio format
            audio_format = self.detect_audio_format(audio_buffer)
            
            
            # Send acknowledgment to phone client
            await self.send_message(websocket, {
                'type': 'audio_ack',
                'chunk_id': data.get('timestamp'),
                'status': 'received',
                'audio_format': audio_format,
                'chunk_size': len(audio_buffer),
                'timestamp': int(time.time() * 1000)
            })
            
            # Forward audio data to site client if connected
            if self.site_socket:
                # Note: In raw WebSocket, we'd need to store the websocket object
                # For now, we'll just log that we would forward it
                print(f"Would forward audio data to site client: {self.site_socket}")
            
            
        except Exception as e:
            print(f"Error processing audio data: {e}")
            print(f"Data sample: {data.get('data', [])[:10] if hasattr(data.get('data', []), '__getitem__') else data.get('data', 'No data')}")
            await self.send_error(websocket, f'Error processing audio: {str(e)}')

    async def handle_get_recommendations(self, websocket, client_id, data):
        """Handle recommendation requests from site client"""
        # Only site client should request recommendations
        if client_id != self.site_socket:
            await self.send_error(websocket, 'Only site client can request recommendations')
            return
        
        try:
            # Generate recommendations (you'll need to implement this)
            recommendations = "Sample recommendations based on conversation topics"
            
            await self.send_message(websocket, {
                'type': 'recommendations',
                'recommendations': recommendations,
                'timestamp': int(time.time() * 1000)
            })
            
            print(f"Sent recommendations to site client")
            
        except Exception as e:
            print(f"Error generating recommendations: {e}")
            await self.send_error(websocket, f'Error generating recommendations: {str(e)}')

    async def handle_clear_audio_chunks(self, websocket, client_id, data):
        """Handle clearing audio chunks list"""
        # Only phone client should clear audio chunks
        if client_id != self.phone_socket:
            await self.send_error(websocket, 'Only phone client can clear audio chunks')
            return
        
        chunks_cleared = len(self.audio_chunks)
        self.audio_chunks.clear()
        
        await self.send_message(websocket, {
            'type': 'audio_chunks_cleared',
            'chunks_cleared': chunks_cleared,
            'timestamp': int(time.time() * 1000)
        })
        
        print(f"Cleared {chunks_cleared} audio chunks")

    async def handle_toggle_audio_playback(self, websocket, client_id, data):
        """Handle audio playback toggle requests"""
        enabled = data.get('enabled')
        current_status = self.toggle_audio_playback(enabled)
        
        await self.send_message(websocket, {
            'type': 'audio_playback_status',
            'enabled': current_status,
            'timestamp': int(time.time() * 1000)
        })


    async def send_message(self, websocket, message):
        """Send a message to the WebSocket client"""
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            print(f"Error sending message: {e}")

    async def send_error(self, websocket, error_message):
        """Send an error message to the WebSocket client"""
        await self.send_message(websocket, {
            'type': 'error',
            'message': error_message,
            'timestamp': int(time.time() * 1000)
        })

    async def close_websocket_server(self):
        """Gracefully close the WebSocket server and clean up all resources"""
        print("\n🔄 Starting graceful shutdown...")
        
        # Set shutdown event
        self.shutdown_event.set()
        
        # Notify all connected clients about shutdown
        if self.active_connections:
            print(f"📤 Notifying {len(self.active_connections)} clients about shutdown...")
            shutdown_message = {
                'type': 'server_shutdown',
                'message': 'Server is shutting down',
                'timestamp': int(time.time() * 1000)
            }
            
            # Send shutdown message to all clients
            for websocket in list(self.active_connections):
                try:
                    await websocket.send(json.dumps(shutdown_message))
                    print(f"Sent shutdown notification to {websocket.remote_address}")
                except Exception as e:
                    print(f"Error sending shutdown message: {e}")
        
        # Close all WebSocket connections
        if self.active_connections:
            print(f"🔌 Closing {len(self.active_connections)} WebSocket connections...")
            for websocket in list(self.active_connections):
                try:
                    await websocket.close(code=1001, reason="Server shutdown")
                    print(f"Closed connection to {websocket.remote_address}")
                except Exception as e:
                    print(f"Error closing connection: {e}")
            
            self.active_connections.clear()
        
        # Clear audio queue
        print("🧹 Clearing audio queue...")
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        # Clear audio chunks
        print(f"🗑️ Clearing {len(self.audio_chunks)} audio chunks...")
        self.audio_chunks.clear()
        
        # Reset socket references
        self.phone_socket = None
        self.site_socket = None
        
        # Close the server
        if self.server:
            print("🛑 Stopping WebSocket server...")
            self.server.close()
            await self.server.wait_closed()
            print("✅ Server stopped successfully")
        
        print("✅ Graceful shutdown completed")

    async def start_server(self):
        """Start the WebSocket server"""
        print(f'WebSocket server running on ws://{self.host}:{self.port}')
        print(f'Accessible from network at: ws://0.0.0.0:{self.port}')
        print(f'Server is binding to all interfaces (0.0.0.0)')
        
        # Start the WebSocket server
        self.server = await websockets.serve(
            self.handle_client, 
            self.host, 
            self.port,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=10
        )
        
        print('Server started successfully. Waiting for connections...')
        print('🎵 Audio processing is ready')
        print('Press Ctrl+C to gracefully shutdown the server')
        
        try:
            # Keep the server running until shutdown event
            await self.shutdown_event.wait()
        except KeyboardInterrupt:
            print("\n⚠️ Keyboard interrupt received")
        finally:
            await self.close_websocket_server()

def main():
    """Main function to start the WebSocket server"""
    port = int(os.environ.get('PORT', 3001))
    
    server = WebSocketServer(host='0.0.0.0', port=port)
    
    # Set up signal handlers for graceful shutdown
    def shutdown_handler(signum, frame):
        print(f'\n⚠️ Received signal {signum}, initiating graceful shutdown...')
        # Set the shutdown event to trigger graceful shutdown
        exit(0)

    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    try:
        print("🚀 Starting WebSocket server...")
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        print('\n⚠️ Keyboard interrupt received, shutting down...')
    except Exception as e:
        print(f'❌ Server error: {e}')
        import traceback
        traceback.print_exc()
    finally:
        print('👋 Server process ended')

if __name__ == '__main__':
    main()
