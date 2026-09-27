import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';

const TriggerCenter = () => {
  const [triggers, setTriggers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTriggers = async () => {
      try {
        const response = await apiClient.get('/api/triggers');
        setTriggers(response.data.triggers || []);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch triggers');
        setLoading(false);
      }
    };
    fetchTriggers();
  }, []);

  if (loading) return <div className="p-4">Loading triggers...</div>;
  if (error) return <div className="p-4 text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-gray-900">Trigger Center</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {triggers.map((trigger, i) => (
          <div key={i} className="bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-2">{trigger.name || trigger.id || `Trigger ${i}`}</h3>
            <pre className="bg-gray-50 p-2 rounded text-xs overflow-auto">
              {JSON.stringify(trigger, null, 2)}
            </pre>
          </div>
        ))}
        {triggers.length === 0 && <p className="text-gray-500">No triggers found.</p>}
      </div>
    </div>
  );
};

export default TriggerCenter;
