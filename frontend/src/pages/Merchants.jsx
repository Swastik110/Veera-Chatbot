import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';

const Merchants = () => {
  const [merchants, setMerchants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMerchants = async () => {
      try {
        const response = await apiClient.get('/api/merchants');
        setMerchants(response.data.merchants || []);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch merchants');
        setLoading(false);
      }
    };
    fetchMerchants();
  }, []);

  if (loading) return <div className="p-4">Loading merchants...</div>;
  if (error) return <div className="p-4 text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-gray-900">Merchants</h1>
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">City</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rating</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {merchants.map((merchant) => (
              <tr key={merchant.merchant_id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{merchant.merchant_id}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{merchant.name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{merchant.category}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{merchant.city}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                    merchant.subscription_status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                  }`}>
                    {merchant.subscription_status}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{merchant.rating}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Merchants;
