# Real-Time Audio Streaming Setup

This app now supports real-time audio streaming to a WebSocket server. Here's how to set it up:

## Features

- **Real-time audio capture** with visual feedback
- **WebSocket streaming** to localhost:3000
- **Automatic reconnection** if connection is lost
- **Audio chunking** for efficient streaming
- **Connection status** indicator in the UI

## Setup Instructions

### 1. Install Dependencies

First, install the app dependencies:
```bash
npm install
```

### 2. Start the WebSocket Server

In a separate terminal, navigate to the project directory and start the WebSocket server:

```bash
# Copy the server package.json
cp server-package.json package.json

# Install server dependencies
npm install

# Start the WebSocket server
npm start
```

The server will start on `ws://localhost:3000` and will:
- Accept audio chunks from the mobile app
- Save complete audio recordings to a `recordings/` folder
- Provide connection status and acknowledgments

### 3. Run the Mobile App

In another terminal, start the Expo development server:

```bash
# Reset package.json to original
git checkout package.json

# Start the app
npm start
```

### 4. Test the Audio Streaming

1. Open the app on your device/emulator
2. Grant microphone permissions when prompted
3. Tap the center button to start recording
4. The app will automatically connect to the WebSocket server
5. Audio will be streamed in real-time to the server
6. Check the server terminal for incoming audio chunks
7. When you stop recording, the complete audio file will be saved

## How It Works

### Audio Capture
- Uses Expo AV for high-quality audio recording
- Captures audio at 44.1kHz, mono channel
- Provides real-time volume visualization

### WebSocket Streaming
- Connects to `ws://localhost:3000` on app startup
- Streams audio data in 4KB chunks every 100ms
- Includes metadata: timestamp, sample rate, channels
- Handles reconnection automatically

### Server Processing
- Receives audio chunks and reconstructs the complete audio
- Saves final audio files as WAV format
- Provides connection status and error handling

## Configuration

You can modify the WebSocket connection settings in `app/(tabs)/index.tsx`:

```typescript
wsServiceRef.current = new WebSocketService({
  url: 'ws://localhost:3000',        // Server URL
  reconnectInterval: 3000,           // Reconnect delay (ms)
  maxReconnectAttempts: 5,           // Max reconnection attempts
  chunkSize: 4096,                   // Audio chunk size (bytes)
});
```

## Troubleshooting

### Connection Issues
- Ensure the WebSocket server is running on port 3000
- Check that no firewall is blocking the connection
- Use the "Reconnect" button in the app if connection fails

### Audio Quality
- Adjust the sample rate and bit rate in the recording options
- Modify chunk size for different latency/quality tradeoffs
- Check microphone permissions are granted

### Performance
- Reduce chunk size for lower latency
- Increase update interval for better performance
- Monitor server logs for connection issues

## File Structure

```
├── app/(tabs)/index.tsx          # Main app with audio streaming
├── services/WebSocketService.ts  # WebSocket client service
├── websocket-server.js           # WebSocket server
├── server-package.json           # Server dependencies
└── recordings/                   # Saved audio files (created automatically)
```

## Next Steps

- Implement audio processing on the server side
- Add real-time transcription capabilities
- Support multiple concurrent connections
- Add audio format conversion options

