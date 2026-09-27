import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';

const Settings = () => {
  const [metadata, setMetadata] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHealthAndMeta = async () => {
      try {
        const metaRes = await apiClient.get('/v1/metadata');
        setMetadata(metaRes.data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchHealthAndMeta();
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-gray-900">Settings</h1>
      
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium mb-4">System Information</h2>
        {loading ? (
          <p>Loading...</p>
        ) : (
          <pre className="bg-gray-50 p-4 rounded text-sm overflow-auto">
            {JSON.stringify(metadata, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
};

export default Settings;
