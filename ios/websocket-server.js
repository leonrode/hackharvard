const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

// Create WebSocket server
const wss = new WebSocket.Server({ port: 3000 });

console.log('WebSocket server running on ws://localhost:3000');  

// Store received audio chunks
let audioChunks = [];
let isRecording = false;

wss.on('connection', function connection(ws) {
  console.log('Client connected');
  
  // Reset audio chunks for new connection
  audioChunks = [];
  isRecording = false;

  ws.on('message', function incoming(data) {
    try {
      const message = JSON.parse(data);
      
      if (message.type === 'register_client') {
        // Handle client registration
        console.log(`Client registered: ${message.client_type}`);
        console.log(`Capabilities:`, message.capabilities);
        
        // Send registration acknowledgment
        ws.send(JSON.stringify({
          type: 'register_ack',
          client_type: message.client_type,
          status: 'registered',
          timestamp: Date.now(),
          server_info: {
            audio_format: 'raw',
            supported_sample_rates: [16000, 44100],
            max_chunk_size: 1024 * 1024 // 1MB
          }
        }));
        
      } else if (message.type === 'audio_chunk') {
        console.log(`Received audio chunk: ${message.data.length} bytes, timestamp: ${message.timestamp}, client: ${message.client_type || 'unknown'}`);
        
        // Convert array back to buffer
        const audioBuffer = Buffer.from(message.data);
        audioChunks.push(audioBuffer);
        
        // Send acknowledgment back to client
        ws.send(JSON.stringify({
          type: 'chunk_ack',
          chunkId: message.timestamp,
          status: 'received',
          client_type: message.client_type
        }));
        
        // If this is the first chunk, start recording
        if (!isRecording) {
          isRecording = true;
          console.log('Started recording audio stream...');
        }
      } else if (message.type === 'audio_level') {
        // Handle real-time audio level data
        console.log(`Audio level: ${Math.round(message.volume * 100)}%, metering: ${message.metering?.toFixed(2) || 'N/A'}dB`);
        
        // Send acknowledgment back to client
        ws.send(JSON.stringify({
          type: 'level_ack',
          volume: message.volume,
          timestamp: message.timestamp,
          status: 'received'
        }));
      } else if (message.type === 'audio_chunk') {
        // Handle real-time audio chunks
        console.log(`Received audio chunk: ${message.size} bytes, volume: ${Math.round(message.volume * 100)}%, metering: ${message.metering?.toFixed(2) || 'N/A'}dB`);
        
        // Convert base64 back to buffer
        const audioBuffer = Buffer.from(message.data, 'base64');
        audioChunks.push(audioBuffer);
        
        // Send acknowledgment back to client
        ws.send(JSON.stringify({
          type: 'chunk_ack',
          size: message.size,
          volume: message.volume,
          timestamp: message.timestamp,
          status: 'received'
        }));
        
        // If this is the first chunk, start recording
        if (!isRecording) {
          isRecording = true;
          console.log('Started real-time audio streaming...');
        }
      } else if (message.type === 'audio_data') {
        // Handle real-time audio data (legacy)
        console.log(`Received audio data: ${message.size} bytes, timestamp: ${message.timestamp}`);
        
        // Convert base64 back to buffer
        const audioBuffer = Buffer.from(message.data, 'base64');
        audioChunks.push(audioBuffer);
        
        // Send acknowledgment back to client
        ws.send(JSON.stringify({
          type: 'audio_ack',
          size: message.size,
          timestamp: message.timestamp,
          status: 'received'
        }));
        
        // If this is the first chunk, start recording
        if (!isRecording) {
          isRecording = true;
          console.log('Started recording audio stream...');
        }
      } else if (message.type === 'audio_file') {
        // Handle complete audio file
        console.log(`Received complete audio file: ${message.size} bytes, timestamp: ${message.timestamp}`);
        
        // Convert base64 back to buffer
        const audioBuffer = Buffer.from(message.data, 'base64');
        
        // Save the complete audio file immediately
        const filename = `complete_audio_${Date.now()}.wav`;
        const filepath = path.join(__dirname, 'recordings', filename);
        
        // Create recordings directory if it doesn't exist
        const recordingsDir = path.join(__dirname, 'recordings');
        if (!fs.existsSync(recordingsDir)) {
          fs.mkdirSync(recordingsDir, { recursive: true });
        }
        
        fs.writeFileSync(filepath, audioBuffer);
        console.log(`Complete audio file saved to: ${filepath}`);
        
        // Send acknowledgment back to client
        ws.send(JSON.stringify({
          type: 'file_ack',
          size: message.size,
          filename: filename,
          timestamp: message.timestamp,
          status: 'saved'
        }));
      }
    } catch (error) {
      console.error('Error processing message:', error);
    }
  });

  ws.on('close', function close() {
    console.log('Client disconnected');
    
    // Save the complete audio file when client disconnects
    if (audioChunks.length > 0) {
      const completeAudio = Buffer.concat(audioChunks);
      const filename = `audio_${Date.now()}.wav`;
      const filepath = path.join(__dirname, 'recordings', filename);
      
      // Create recordings directory if it doesn't exist
      const recordingsDir = path.join(__dirname, 'recordings');
      if (!fs.existsSync(recordingsDir)) {
        fs.mkdirSync(recordingsDir, { recursive: true });
      }
      
      fs.writeFileSync(filepath, completeAudio);
      console.log(`Audio saved to: ${filepath}`);
      console.log(`Total chunks received: ${audioChunks.length}`);
      console.log(`Total audio size: ${completeAudio.length} bytes`);
    }
    
    isRecording = false;
    audioChunks = [];
  });

  ws.on('error', function error(err) {
    console.error('WebSocket error:', err);
  });

  // Send welcome message
  ws.send(JSON.stringify({
    type: 'welcome',
    message: 'Connected to audio streaming server',
    timestamp: Date.now()
  }));
});

// Handle server shutdown gracefully
process.on('SIGINT', () => {
  console.log('\nShutting down WebSocket server...');
  wss.close(() => {
    console.log('Server closed');
    process.exit(0);
  });
});
