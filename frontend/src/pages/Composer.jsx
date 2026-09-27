import React, { useState } from 'react';
import apiClient from '../api/client';

const Composer = () => {
  const [formData, setFormData] = useState({
    category_slug: '',
    merchant_id: '',
    trigger_id: '',
    customer_id: ''
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await apiClient.post('/api/compose', formData);
      setResult(response.data);
    } catch (err) {
      setError('Failed to compose message');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-gray-900">AI Composer</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium mb-4">Compose Request</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Category Slug</label>
              <input type="text" name="category_slug" value={formData.category_slug} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2" placeholder="e.g. food_dining" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Merchant ID</label>
              <input type="text" name="merchant_id" value={formData.merchant_id} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Trigger ID</label>
              <input type="text" name="trigger_id" value={formData.trigger_id} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Customer ID</label>
              <input type="text" name="customer_id" value={formData.customer_id} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2" required />
            </div>
            <button type="submit" disabled={loading} className="w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 focus:outline-none disabled:opacity-50">
              {loading ? 'Composing...' : 'Compose Message'}
            </button>
          </form>
        </div>

        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium mb-4">Result</h2>
          {error && <p className="text-red-500">{error}</p>}
          {result ? (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-medium text-gray-500">Body</h3>
                <p className="mt-1 text-sm text-gray-900 bg-gray-50 p-3 rounded">{result.body}</p>
              </div>
              {result.cta && (
                <div>
                  <h3 className="text-sm font-medium text-gray-500">CTA</h3>
                  <p className="mt-1 text-sm text-indigo-600 font-medium">{result.cta}</p>
                </div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h3 className="text-sm font-medium text-gray-500">Send As</h3>
                  <p className="mt-1 text-sm text-gray-900">{result.send_as}</p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-gray-500">Suppression Key</h3>
                  <p className="mt-1 text-sm text-gray-900">{result.suppression_key}</p>
                </div>
              </div>
              <div>
                <h3 className="text-sm font-medium text-gray-500">Rationale</h3>
                <p className="mt-1 text-sm text-gray-600 italic">{result.rationale}</p>
              </div>
            </div>
          ) : (
            <p className="text-gray-500 text-sm">Fill the form and submit to see the generated message.</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Composer;
