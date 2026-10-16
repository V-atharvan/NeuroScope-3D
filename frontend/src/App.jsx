import React, { useState, useEffect } from 'react';
import DisclaimerBanner from './components/DisclaimerBanner';
import Header from './components/Header';
import Dashboard from './pages/Dashboard';
import { getHealth } from './services/api';

export default function App() {
  const [backendHealth, setBackendHealth] = useState(null);

  useEffect(() => {
    getHealth()
      .then((data) => setBackendHealth(data))
      .catch((err) => {
        console.warn('Backend currently offline or starting:', err.message);
      });
  }, []);

  return (
    <div className="neuroscope-app">
      <DisclaimerBanner />
      <div className="app-container">
        <Header backendHealth={backendHealth} />
        <Dashboard backendHealth={backendHealth} />
      </div>
    </div>
  );
}
