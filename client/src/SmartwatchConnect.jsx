import React, { useState } from 'react'

// parse heart rate measurement
function parseHeartRate(value) {
  const data = value; // value is a DataView in browser
  try {
    const flags = data.getUint8(0);
    const hrFormat = flags & 0x1;
    let hr;
    if (hrFormat === 0) {
      hr = data.getUint8(1);
    } else {
      hr = data.getUint16(1, true);
    }
    return hr;
  } catch (e) {
    console.error('HR parse err', e);
    return null;
  }
}

export default function SmartwatchConnect({ onHealthData }) {
  const [connected, setConnected] = useState(false)
  const [deviceName, setDeviceName] = useState(null)

  async function connect() {
    if (!navigator.bluetooth) {
      alert('Web Bluetooth not supported in this browser. Use Chrome on Android or desktop.');
      return;
    }
    try {
      const device = await navigator.bluetooth.requestDevice({ filters: [{ services: ['heart_rate'] }], optionalServices: ['battery_service'] });
      setDeviceName(device.name || 'BLE Device');
      const server = await device.gatt.connect();
      const service = await server.getPrimaryService('heart_rate');
      const char = await service.getCharacteristic('heart_rate_measurement');

      await char.startNotifications();
      char.addEventListener('characteristicvaluechanged', (ev) => {
        const value = ev.target.value; // DataView
        const hr = parseHeartRate(value);
        if (hr) {
          const payload = { heartRate: hr, timestamp: new Date().toISOString(), source: 'ble' };
          onHealthData(payload);
        }
      });

      device.addEventListener('gattserverdisconnected', () => setConnected(false));
      setConnected(true);
    } catch (err) {
      console.error('BLE connect error', err);
      alert('Could not connect: ' + (err.message || err));
    }
  }

  return (
    <div>
      <h3>Connect a smartwatch / BLE heart-rate sensor</h3>
      <p>Browser support is limited (Chrome desktop/Android). For Apple Watch use a native companion mobile app.</p>
      <button onClick={connect} disabled={connected}>{connected ? 'Connected' : 'Connect via Web Bluetooth'}</button>
      {connected && <p>Connected to {deviceName}</p>}
    </div>
  )
}
