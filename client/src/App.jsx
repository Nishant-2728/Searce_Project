import React, { useState, useEffect, useRef } from 'react'
import MoodQuiz from './MoodQuiz'
import SmartwatchConnect from './SmartwatchConnect'

const OPENWEATHER_KEY = import.meta.env.VITE_OPENWEATHER_KEY;

export default function App() {
  const [locationData, setLocationData] = useState(null);
  const [weather, setWeather] = useState(null);
  const [moodResult, setMoodResult] = useState(null);
  const [healthData, setHealthData] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    // open websocket to backend for real-time suggestions
    const url = (location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.hostname + ':4000/ws/health';
    try {
      const ws = new WebSocket(url);
      ws.addEventListener('open', () => console.log('WS open'));
      ws.addEventListener('message', ev => {
        try { const msg = JSON.parse(ev.data); console.log('WS message', msg); }
        catch(e){ console.log('WS raw', ev.data) }
      });
      wsRef.current = ws;
      return () => ws.close();
    } catch (e) { console.warn('WebSocket init failed', e); }
  }, []);

  function sendHealthOverWS(payload) {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }

  async function requestLocation() {
    if (!navigator.geolocation) {
      alert('Geolocation not supported by this browser.');
      return;
    }
    navigator.geolocation.getCurrentPosition(async (pos) => {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      const localTime = new Date().toISOString();
      setLocationData({ lat, lon, localTime });

      // Fetch weather
      try {
        if (!OPENWEATHER_KEY) {
          console.warn('VITE_OPENWEATHER_KEY not set in client environment.');
          return;
        }
        const resp = await fetch(
          `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&units=metric&appid=${OPENWEATHER_KEY}`
        );
        const data = await resp.json();
        setWeather(data);
      } catch (err) {
        console.error('Weather fetch failed', err);
      }
    }, (err) => {
      alert('Location permission denied or error: ' + err.message);
    });
  }

  async function handleMoodFinish(result) {
    setMoodResult(result); // {score, answers}
  }

  function handleHealthUpdate(h) {
    setHealthData(h); // e.g. { heartRate, timestamp }
    const payload = { userId: 'anon', ...h, location: locationData, mood: moodResult };
    // POST to server
    fetch('/api/health-data', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    }).catch(console.error);
    // send real-time via WS
    sendHealthOverWS(payload);
  }

  function computeSuggestion() {
    const hr = healthData?.heartRate ?? null;
    const mood = moodResult?.score ?? 50;
    const temp = weather?.main?.temp;
    const suggestions = [];
    if (mood < 40 || (hr && hr > 100)) {
      suggestions.push('Try a 5-minute guided breathing exercise to reduce stress.');
    } else {
      suggestions.push('You look calm — try a balanced meal: protein + veggies.');
    }
    if (temp && temp > 30) suggestions.push('Hydrate: temperature is high.');
    return suggestions;
  }

  return (
    <div>
      <h2>Searce — Personalized Onboarding</h2>

      <div className="card">
        {!locationData && (
          <div>
            <p>To personalize recommendations, please share your location.</p>
            <button onClick={requestLocation}>Share my location</button>
          </div>
        )}

        {locationData && weather && (
          <div>
            <p>Location detected: {locationData.lat.toFixed(4)}, {locationData.lon.toFixed(4)}</p>
            <p>Weather: {weather.weather[0].description}, {weather.main.temp}°C</p>
            <p>Local time: {new Date(locationData.localTime).toLocaleString()}</p>
            <button onClick={() => setLocationData(null)}>Reset location</button>
          </div>
        )}
      </div>

      <div className="card">
        <MoodQuiz onFinish={handleMoodFinish} />
        {moodResult && <p>Mood score: {moodResult.score}</p>}
      </div>

      <div className="card">
        <SmartwatchConnect onHealthData={handleHealthUpdate} />
        {healthData && <p>Latest HR: {healthData.heartRate} bpm</p>}
      </div>

      <div className="card">
        <h3>Suggestions</h3>
        <ul>
          {computeSuggestion().map((s, i) => <li key={i}>{s}</li>)}
        </ul>
      </div>

    </div>
  )
}
