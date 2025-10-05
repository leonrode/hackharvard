## echopilot

Real-time topic extraction and recommendations from live audio. The backend ingests audio (e.g., from the mobile app), transcribes and chunks it into topics, and streams topic updates over WebSocket to the web frontend, which renders animated topic cards.

### Architecture
- **backend/**: Python WebSocket server (`backend/mainserver.py`) that manages connections, runs `Transcriber`, `TopicManager`, and `Recommender`, and pushes topic updates.
- **frontend/**: Vite + React app that connects to the backend via WebSocket (see `frontend/src/useWsTopics.js`) and displays live topics.
- **ios/**: Expo React Native app scaffolding to capture/stream audio to the backend (see `ios/websocket-server.js` and app screens).

---

### Prerequisites
- Node.js 18+ and npm
- Python 3.13 (or compatible with your environment)
- (Optional) Xcode / iOS Simulator for the mobile app

---

### Backend: Setup & Run
1) Create and activate a virtual environment
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

2) Install dependencies
```bash
pip install -r requirements.txt
```

3) Run the WebSocket server (defaults to port 3001)
```bash
python mainserver.py
```

- The server listens on `ws://0.0.0.0:3001` and expects a site client to send `{ type: "register_client", client_type: "site" }` on open.
- Topic updates are broadcast with `{ type: "data", data: { topics: [...] } }`.

Environment variables:
- `PORT` (optional): override the default port (3001).

---

### Frontend: Setup & Run
1) Install dependencies
```bash
cd frontend
npm install
```

2) Configure WebSocket URL
Create `frontend/.env` (or `.env.local`) and set the backend URL:
```bash
VITE_WS_URL=ws://localhost:3001
```

3) Start the dev server
```bash
npm run dev
```

The app will connect to `VITE_WS_URL` and show live topic cards. The UI uses animated cards (Framer Motion) with a staggered scroll effect.

---

### iOS App (Optional)
The `ios/` directory contains an Expo project template configured for tabs and a WebSocket helper (`ios/websocket-server.js`). To run it:
```bash
cd ios
npm install
npm run start
```
Then open in iOS Simulator or on-device via Expo Go. Point the app to your backend WebSocket (adjust host/port to your machine on the same network).

---

### Data Flow
1) Mobile app (or another client) streams audio frames to the backend.
2) Backend transcribes, chunks, and aggregates into topics.
3) Backend pushes `{ type: "data" }` messages with topic arrays to the site client.
4) Frontend (`useWsTopics`) receives updates and renders them in `App.jsx`.

---

### Common Commands
Backend (from `backend/`):
```bash
source venv/bin/activate
python mainserver.py
```

Frontend (from `frontend/`):
```bash
npm install
npm run dev
```

iOS (from `ios/`):
```bash
npm install
npm run start
```

---

### Troubleshooting
- Frontend shows "VITE_WS_URL is not set": create `frontend/.env` with `VITE_WS_URL`.
- Cannot connect to backend: confirm the backend is running and that `VITE_WS_URL` host/port are reachable.
- Hook order warnings: ensure React hooks are not called inside loops/conditions. The frontend has been updated accordingly.
- If running on a device: use your computer’s LAN IP in `VITE_WS_URL`, e.g. `ws://192.168.x.x:3001`.

---

### Notes
- Backend logs and components: see `backend/transcriber.py`, `backend/topic_manager.py`, `backend/recommender.py`.
- Frontend WebSocket integration: `frontend/src/useWsTopics.js`. Main UI: `frontend/src/App.jsx` and `frontend/src/App.css`.

