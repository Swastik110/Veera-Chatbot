import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import Merchants from './pages/Merchants';
import ContextExplorer from './pages/ContextExplorer';
import TriggerCenter from './pages/TriggerCenter';
import ChatSimulator from './pages/ChatSimulator';
import Composer from './pages/Composer';
import TestJudge from './pages/TestJudge';
import Settings from './pages/Settings';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="merchants" element={<Merchants />} />
          <Route path="context-explorer" element={<ContextExplorer />} />
          <Route path="trigger-center" element={<TriggerCenter />} />
          <Route path="chat-simulator" element={<ChatSimulator />} />
          <Route path="composer" element={<Composer />} />
          <Route path="test-judge" element={<TestJudge />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
