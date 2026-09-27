import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { Activity, Users, Store, Zap } from 'lucide-react';

const StatCard = ({ title, value, icon: Icon, color }) => (
  <div className="bg-white rounded-lg shadow p-6 flex items-center">
    <div className={`p-3 rounded-full ${color} mr-4`}>
      <Icon className="text-white" size={24} />
    </div>
    <div>
      <p className="text-sm font-medium text-gray-500 truncate">{title}</p>
      <p className="text-2xl font-semibold text-gray-900">{value}</p>
    </div>
  </div>
);

const Overview = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const response = await apiClient.get('/api/dashboard');
        setData(response.data);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch dashboard data');
        setLoading(false);
      }
    };
    fetchDashboard();
  }, []);

  if (loading) return <div className="p-4">Loading overview...</div>;
  if (error) return <div className="p-4 text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-gray-900">Overview</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Merchants" 
          value={data?.merchants || 0} 
          icon={Store} 
          color="bg-blue-500" 
        />
        <StatCard 
          title="Customers" 
          value={data?.customers || 0} 
          icon={Users} 
          color="bg-green-500" 
        />
        <StatCard 
          title="Triggers" 
          value={data?.triggers || 0} 
          icon={Zap} 
          color="bg-yellow-500" 
        />
        <StatCard 
          title="Active Conversations" 
          value={data?.active_conversations || 0} 
          icon={Activity} 
          color="bg-purple-500" 
        />
      </div>

      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">System Stats</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <p className="text-sm text-gray-500">Messages Generated</p>
            <p className="text-xl font-semibold">{data?.messages_generated || 0}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Proactive Actions</p>
            <p className="text-xl font-semibold">{data?.proactive_actions || 0}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Uptime (Seconds)</p>
            <p className="text-xl font-semibold">{data?.uptime_seconds || 0}</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Overview;
