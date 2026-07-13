require('dotenv').config();
const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const http = require('http');
const WebSocket = require('ws');

const app = express();
app.use(cors());
app.use(bodyParser.json());

const PORT = process.env.PORT || 4000;

// In-memory store (replace with DB for production)
const healthStore = {};

// Receive POSTed health datapoint (fallback)
app.post('/api/health-data', (req, res) => {
  const { userId = 'anon', heartRate, timestamp, location, mood } = req.body;
  if (!healthStore[userId]) healthStore[userId] = [];
  const entry = { heartRate, timestamp: timestamp || new Date().toISOString(), location, mood };
  healthStore[userId].push(entry);
  // Optionally prune older points
  if (healthStore[userId].length > 200) healthStore[userId].shift();
  res.json({ ok: true });
});

// Simple suggestions endpoint
app.get('/api/suggestions', (req, res) => {
  const userId = req.query.userId || 'anon';
  const history = healthStore[userId] || [];
  const last = history[history.length - 1];
  const suggestions = [];
  if (!last) {
    suggestions.push('No health data yet. Connect your watch for personalized suggestions.');
    return res.json({ suggestions });
  }
  const hr = last.heartRate;
  if (hr > 100) suggestions.push('High heart rate detected — try a breathing exercise and sit down for 5 minutes.');
  else suggestions.push('Heart rate looks normal.');
  const moodScore = last.mood?.score;
  if (moodScore !== undefined && moodScore < 40) suggestions.push('You reported low mood — consider a calming activity or reach out to a friend.');
  res.json({ suggestions, last });
});

const server = http.createServer(app);
const wss = new WebSocket.Server({ server, path: '/ws/health' });

wss.on('connection', (ws, req) => {
  console.log('WS client connected');
  ws.on('message', (message) => {
    try {
      const json = JSON.parse(message);
      // expect: { userId, heartRate, timestamp, location, mood }
      const userId = json.userId || 'anon';
      if (!healthStore[userId]) healthStore[userId] = [];
      healthStore[userId].push({ heartRate: json.heartRate, timestamp: json.timestamp || new Date().toISOString(), location: json.location, mood: json.mood });
      // compute suggestion and send back
      const reply = computeSuggestionForEntry(healthStore[userId][healthStore[userId].length - 1]);
      ws.send(JSON.stringify({ type: 'suggestion', suggestions: reply }));
    } catch (e) {
      console.error('WS message parse error', e);
    }
  });
  ws.on('close', () => console.log('WS client disconnected'));
});

function computeSuggestionForEntry(entry) {
  const suggestions = [];
  if (!entry) return ['No data'];
  const hr = entry.heartRate;
  if (hr > 100) suggestions.push('High heart rate detected — try a breathing exercise and sit down for 5 minutes.');
  else suggestions.push('Heart rate looks normal.');
  const moodScore = entry.mood?.score;
  if (moodScore !== undefined && moodScore < 40) suggestions.push('Low mood reported — consider a calming activity.');
  return suggestions;
}

server.listen(PORT, () => console.log(`Server listening on ${PORT}`));
