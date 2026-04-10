'use client';

import { useState } from 'react';
import Sidebar from '@/components/Sidebar';
import ChatInterface from '@/components/ChatInterface';
import FileUpload from '@/components/FileUpload';
import TaskDashboard from '@/components/TaskDashboard';

type Tab = 'chat' | 'upload' | 'agents';

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('chat');
  const [sessionId] = useState(() => crypto.randomUUID());

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="flex-1 overflow-hidden">
        {activeTab === 'chat'   && <ChatInterface sessionId={sessionId} />}
        {activeTab === 'upload' && <FileUpload />}
        {activeTab === 'agents' && <TaskDashboard sessionId={sessionId} />}
      </main>
    </div>
  );
}
