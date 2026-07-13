# Searce_Project - multimodal onboarding

This branch adds a basic onboarding flow (geolocation -> weather/time), a quick mood questionnaire, and a Web Bluetooth smartwatch connector that streams heart rate to the backend (via POST and WebSocket).

How to run locally

1) Server

  cd server
  npm install
  # (optional) copy .env.example to .env and adjust PORT
  node server.js

The server listens on port 4000 by default.

2) Client (Vite + React)

  cd client
  npm install
  # create client/.env and add:
  # VITE_OPENWEATHER_KEY=your_openweather_api_key
  npm run dev

Open the client (Vite will show a local URL like http://localhost:5173). Note: the client expects the backend WebSocket on port 4000 (ws://localhost:4000/ws/health).

Notes & next steps
- This is an MVP scaffold. Replace in-memory storage with a database and add authentication for production.
- Web Bluetooth has limited browser support (Chrome desktop/Android). For Apple Watch you will need a native iOS app + HealthKit integration.
- Remove example API keys from repository and keep them in environment variables.

Testing
- Use Chrome on desktop or Android to test the Web Bluetooth flow with a BLE heart-rate monitor.
- If you don't have a device, you can POST sample health JSON to POST /api/health-data to exercise suggestion logic.

