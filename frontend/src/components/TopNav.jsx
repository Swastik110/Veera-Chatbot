import React from 'react';
import { Bell, User } from 'lucide-react';

const TopNav = () => {
  return (
    <header className="flex items-center justify-between px-6 py-4 bg-white border-b">
      <div className="flex items-center">
        <h2 className="text-xl font-semibold text-gray-800">Dashboard</h2>
      </div>
      <div className="flex items-center space-x-4">
        <button className="text-gray-500 hover:text-gray-700">
          <Bell size={20} />
        </button>
        <button className="flex items-center text-sm font-medium text-gray-700 hover:text-gray-900">
          <User size={20} className="mr-2" />
          Admin
        </button>
      </div>
    </header>
  );
};

export default TopNav;
