import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';

const ContextExplorer = () => {
  const [contexts, setContexts] = useState({ category: [], merchant: [], trigger: [], customer: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchContexts = async () => {
      try {
        const response = await apiClient.get('/api/contexts');
        setContexts(response.data || { category: [], merchant: [], trigger: [], customer: [] });
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch contexts');
        setLoading(false);
      }
    };
    fetchContexts();
  }, []);

  if (loading) return <div className="p-4">Loading contexts...</div>;
  if (error) return <div className="p-4 text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-gray-900">Context Explorer</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium mb-4">Categories Contexts</h2>
          <pre className="bg-gray-50 p-4 rounded text-sm overflow-auto h-64">
            {JSON.stringify(contexts.category, null, 2)}
          </pre>
        </div>
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium mb-4">Merchant Contexts</h2>
          <pre className="bg-gray-50 p-4 rounded text-sm overflow-auto h-64">
            {JSON.stringify(contexts.merchant, null, 2)}
          </pre>
        </div>
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium mb-4">Trigger Contexts</h2>
          <pre className="bg-gray-50 p-4 rounded text-sm overflow-auto h-64">
            {JSON.stringify(contexts.trigger, null, 2)}
          </pre>
        </div>
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium mb-4">Customer Contexts</h2>
          <pre className="bg-gray-50 p-4 rounded text-sm overflow-auto h-64">
            {JSON.stringify(contexts.customer, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};

export default ContextExplorer;
