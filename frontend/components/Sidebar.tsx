'use client';

import { BrainCircuit, MessageSquare, Upload, Cpu, Github, Zap } from 'lucide-react';
import clsx from 'clsx';

type Tab = 'chat' | 'upload' | 'agents';

interface SidebarProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

const NAV_ITEMS = [
  {
    id: 'chat' as Tab,
    label: 'AI Chat',
    icon: MessageSquare,
    description: 'Chat · RAG · Agent mode',
  },
  {
    id: 'upload' as Tab,
    label: 'Documents',
    icon: Upload,
    description: 'Upload & ingest PDFs',
  },
  {
    id: 'agents' as Tab,
    label: 'Task Agents',
    icon: Cpu,
    description: 'Multi-agent dashboard',
  },
];

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <aside className="w-64 flex-shrink-0 flex flex-col h-full border-r"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      {/* Logo */}
      <div className="p-5 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
            style={{ background: 'linear-gradient(135deg, #5a7eff 0%, #9b6dff 100%)' }}>
            <BrainCircuit className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white leading-tight">Autonomous AI</h1>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Multi-Agent + RAG System</p>
          </div>
        </div>
      </div>

      {/* Status pill */}
      <div className="px-4 pt-4">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs"
          style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)' }}>
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse-slow" />
          <span style={{ color: '#86efac' }}>Backend connected</span>
          <Zap className="w-3 h-3 ml-auto" style={{ color: '#86efac' }} />
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 pt-4 space-y-1">
        <p className="text-[10px] font-semibold uppercase tracking-widest px-3 pb-2"
          style={{ color: 'var(--text-muted)' }}>
          Workspace
        </p>
        {NAV_ITEMS.map(({ id, label, icon: Icon, description }) => (
          <button
            key={id}
            id={`nav-${id}`}
            onClick={() => onTabChange(id)}
            className={clsx('nav-item w-full text-left', activeTab === id && 'active')}
          >
            <div className={clsx(
              'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-colors',
              activeTab === id
                ? 'bg-blue-500/20'
                : 'bg-white/5'
            )}>
              <Icon className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium">{label}</div>
              <div className="text-[11px] truncate" style={{ color: 'var(--text-muted)' }}>
                {description}
              </div>
            </div>
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-white/80">v1.0.0</p>
            <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>Production Ready</p>
          </div>
          <div className="flex gap-1">
            <div className="w-2 h-2 rounded-full" style={{ background: '#5a7eff' }} />
            <div className="w-2 h-2 rounded-full" style={{ background: '#9b6dff' }} />
            <div className="w-2 h-2 rounded-full" style={{ background: '#22c55e' }} />
          </div>
        </div>
      </div>
    </aside>
  );
}
