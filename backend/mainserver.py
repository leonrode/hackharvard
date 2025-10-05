import asyncio

import websockets
import json
import os
import time
import queue
import uuid
from datetime import datetime
import sys
from audio_streams import WebSocketAudioStream
import base64
import struct
import signal

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

        self.audio_stream = WebSocketAudioStream(None)
        self.audio_websocket = None
        
        # Service instances
        self.topic_manager = TopicManager()
        self.transcriber = Transcriber(self.topic_manager, on_working_buffer_update=lambda x: print(f"Working buffer: {x}"), on_dump=lambda x: print(f"Dumped text: {x}"), on_chunks_produced=self.on_chunk_callback)
        self.recommender = Recommender()
        
        # Server state
        self.server = None
        self.active_connections = set()
        self.shutdown_event = asyncio.Event()

    def on_chunk_callback(self, chunks):

        topics = [self.topic_manager.get_topic_from_topic_id(topic_id) for topic_id in chunks.keys()]

        recommendations = self.recommender.recommend(topics)



        self.transcriber.previous_recommendations = recommendations


        # now i would like to send this data over the site websocket
        # Schedule the async function as a task in the current event loop
        asyncio.create_task(self.send_message(self.site_socket, {
                "type": "data",
                "data": {
                    "topics": [{
                        "topic_key": topic_id,
                        "topic_summary": topic.description,
                        "content_stack": [{"blurb": chunk.blurb, "content": chunk.content} for chunk in topic.chunk_stack],
                        "recommendations": recommendations[topic_id],
                    } for (topic_id, topic) in topics]
                }
            }))


    async def start_server(self):
        """Start the WebSocket server"""
        print(f'WebSocket server running on ws://{self.host}:{self.port}')
        print(f'Server is binding to all interfaces (0.0.0.0)')
        
        # Start the WebSocket server
        self.server = await websockets.serve(
            self.handle_client, 
            self.host, 
            self.port,
            ping_interval=30,
            ping_timeout=50,
            close_timeout=50
        )
        
        print('Server started successfully. Waiting for connections...')
        print('Press Ctrl+C to gracefully shutdown the server')
        
        try:
            # Keep the server running until shutdown event
            await self.shutdown_event.wait()
        except KeyboardInterrupt:
            print("\n⚠️ Keyboard interrupt received")
        finally:
            await self.close_websocket_server()


    def queue_audio_data(self, audio_data):
        """Queue audio data for playback"""
        if not self.audio_queue.full():
            self.audio_queue.put(audio_data)

        print(f"Total audio queue size: {self.audio_queue.qsize()}")
        
        # Process audio directly with transcriber
        self.transcriber._transcription_loop(self.audio_queue.get())

    async def handle_client(self, websocket, path=None):
        client_address = websocket.remote_address
        client_id = str(uuid.uuid4())

        
        print(f"New connection attempt from {client_address}")

        try:
            # Send welcome message
            welcome_message = {
                'type': 'welcome',
                'message': 'Connected to real-time recommendations server',
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
        else:
            await self.send_error(websocket, f'Unknown message type: {message_type}')

    async def handle_register_client(self, websocket, client_id, data):
        """Handle client registration"""
        client_type = data.get('client_type', 'unknown')
        print(f"Registering client {client_id} with type {client_type}")
        
        # Check if we can accept this connection

        if client_type == 'site':
            self.site_socket = websocket
            print(f"Site client connected: {self.site_socket}")
            await self.send_message(websocket, {
                'type': 'connected',
                'client_type': 'site',
                'message': 'Site client connected successfully'
            })

            
        else:
            await self.send_message(websocket, {
                'type': 'connected',
                'client_type': 'phone',
                'message': 'Phone client connected successfully'
            })

            self.audio_websocket = websocket




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

    async def handle_audio_chunk(self, websocket, client_id, data):
        """Handle audio chunk messages from phone client"""


        d = base64.b64decode(data["data"])



        self.transcriber._transcription_loop(d)

        await self.send_message(websocket, {
            'type': 'audio_chunk_received',
            'message': 'Audio chunk received successfully',
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
