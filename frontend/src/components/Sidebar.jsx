import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  Home, 
  Store, 
  Database, 
  Zap, 
  MessageSquare, 
  Edit3, 
  CheckCircle, 
  Settings 
} from 'lucide-react';

const navItems = [
  { path: '/', name: 'Overview', icon: <Home size={20} /> },
  { path: '/merchants', name: 'Merchants', icon: <Store size={20} /> },
  { path: '/context-explorer', name: 'Context Explorer', icon: <Database size={20} /> },
  { path: '/trigger-center', name: 'Trigger Center', icon: <Zap size={20} /> },
  { path: '/chat-simulator', name: 'Chat Simulator', icon: <MessageSquare size={20} /> },
  { path: '/composer', name: 'AI Composer', icon: <Edit3 size={20} /> },
  { path: '/test-judge', name: 'Test & Judge', icon: <CheckCircle size={20} /> },
  { path: '/settings', name: 'Settings', icon: <Settings size={20} /> },
];

const Sidebar = () => {
  return (
    <div className="flex flex-col w-64 bg-white border-r h-full">
      <div className="flex items-center justify-center h-16 border-b">
        <span className="text-xl font-bold text-indigo-600">magicpin AI</span>
      </div>
      <div className="flex-1 overflow-y-auto py-4">
        <nav className="space-y-1 px-2">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center px-4 py-2 text-sm font-medium rounded-md ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-600'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              <span className="mr-3">{item.icon}</span>
              {item.name}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
};

export default Sidebar;
