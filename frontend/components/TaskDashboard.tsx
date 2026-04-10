'use client';

import { useState, useRef, useEffect } from 'react';
import { Play, Loader2, ChevronDown, ChevronRight, CheckCircle, XCircle, Clock, Brain, Cpu, Bug, Star, Zap } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import clsx from 'clsx';

interface AgentStepEvent {
  agent: string;
  step_number: number;
  input: string;
  output: string;
  status: string;
  duration_ms?: number;
  error?: string;
}

interface TaskState {
  status: 'idle' | 'running' | 'complete' | 'error';
  plan: { step_number: number; description: string; agent: string }[];
  steps: AgentStepEvent[];
  finalOutput: string;
  totalDuration: number;
}

const AGENT_CONFIG: Record<string, { label: string; color: string; icon: React.ElementType; bg: string }> = {
  PlannerAgent:  { label: 'Planner',  color: '#f59e0b', icon: Brain,  bg: 'rgba(245,158,11,0.1)' },
  ExecutorAgent: { label: 'Executor', color: '#3b82f6', icon: Cpu,    bg: 'rgba(59,130,246,0.1)' },
  DebugAgent:    { label: 'Debug',    color: '#ef4444', icon: Bug,    bg: 'rgba(239,68,68,0.1)' },
  ReviewerAgent: { label: 'Reviewer', color: '#22c55e', icon: Star,   bg: 'rgba(34,197,94,0.1)' },
};

const EXAMPLE_TASKS = [
  'Write a Python function to parse CSV files and convert to JSON',
  'Create a REST API design for a todo app with CRUD endpoints',
  'Explain how to optimize a PostgreSQL query with proper indexing',
  'Write unit tests for a user authentication module',
];

interface TaskDashboardProps {
  sessionId: string;
}

export default function TaskDashboard({ sessionId }: TaskDashboardProps) {
  const [task, setTask] = useState('');
  const [taskState, setTaskState] = useState<TaskState>({
    status: 'idle',
    plan: [],
    steps: [],
    finalOutput: '',
    totalDuration: 0,
  });
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set(['review']));
  const stepsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    stepsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [taskState.steps]);

  const runTask = async () => {
    if (!task.trim() || taskState.status === 'running') return;

    setTaskState({ status: 'running', plan: [], steps: [], finalOutput: '', totalDuration: 0 });
    setExpandedSteps(new Set());

    try {
      const res = await fetch('/api/agents/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, session_id: sessionId, stream: true }),
      });

      if (!res.ok || !res.body) throw new Error(`Server error: ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6));

            if (event.type === 'plan') {
              setTaskState(p => ({ ...p, plan: event.plan || [] }));
              // Auto-expand planner step
              setExpandedSteps(prev => new Set([...prev, `${event.step?.agent}-${event.step?.step_number}`]));
            }

            else if (event.type === 'agent_step' && event.step) {
              setTaskState(p => ({ ...p, steps: [...p.steps, event.step] }));
            }

            else if (event.type === 'review' && event.step) {
              setTaskState(p => ({ ...p, steps: [...p.steps, event.step] }));
              setExpandedSteps(prev => new Set([...prev, 'review']));
            }

            else if (event.type === 'complete') {
              setTaskState(p => ({
                ...p,
                status: 'complete',
                finalOutput: event.final_output || '',
                totalDuration: event.total_duration_ms || 0,
              }));
            }

            else if (event.type === 'error') {
              setTaskState(p => ({ ...p, status: 'error', finalOutput: event.message }));
            }

          } catch { /* ignore */ }
        }
      }
    } catch (err: any) {
      setTaskState(p => ({ ...p, status: 'error', finalOutput: err.message }));
    }
  };

  const toggleStep = (key: string) => {
    setExpandedSteps(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const formatMs = (ms: number) => ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-base)' }}>

      {/* Header */}
      <div className="shrink-0 px-8 py-6 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-3 mb-1">
          <Zap className="w-5 h-5" style={{ color: '#5a7eff' }} />
          <h1 className="text-lg font-bold text-white">Task Agent Dashboard</h1>
        </div>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Planner → Executor → Debug → Reviewer · Real-time agent execution
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-8 space-y-6">

        {/* Input */}
        <div className="glass rounded-2xl p-5 space-y-4 animate-fade-in">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider mb-2 block"
              style={{ color: 'var(--text-muted)' }}>
              Task Description
            </label>
            <textarea
              id="task-input"
              value={task}
              onChange={e => setTask(e.target.value)}
              placeholder="Describe a task for the AI agents..."
              rows={3}
              disabled={taskState.status === 'running'}
              className="input text-sm leading-relaxed"
            />
          </div>

          {/* Example Tasks */}
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_TASKS.map((t, i) => (
              <button
                key={i}
                onClick={() => setTask(t)}
                className="text-xs px-3 py-1.5 rounded-lg transition-colors"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-secondary)',
                }}
              >
                {t.slice(0, 40)}…
              </button>
            ))}
          </div>

          <button
            id="run-task-btn"
            onClick={runTask}
            disabled={!task.trim() || taskState.status === 'running'}
            className="btn-primary w-full justify-center disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {taskState.status === 'running' ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Running agents...</>
            ) : (
              <><Play className="w-4 h-4" /> Run Task</>
            )}
          </button>
        </div>

        {/* Plan */}
        {taskState.plan.length > 0 && (
          <div className="glass rounded-2xl p-5 space-y-3 animate-slide-up">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Brain className="w-4 h-4" style={{ color: '#f59e0b' }} />
              Execution Plan ({taskState.plan.length} steps)
            </h3>
            <div className="space-y-2">
              {taskState.plan.map((step, i) => {
                const cfg = AGENT_CONFIG[step.agent] || AGENT_CONFIG.ExecutorAgent;
                const Icon = cfg.icon;
                const done = taskState.steps.some(
                  s => s.agent === step.agent && s.step_number === step.step_number && s.status === 'success'
                );
                return (
                  <div key={i} className="flex items-center gap-3 py-2 px-3 rounded-xl"
                    style={{ background: 'rgba(255,255,255,0.03)' }}>
                    <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                      style={{ background: cfg.bg, color: cfg.color }}>
                      {done ? '✓' : step.step_number}
                    </div>
                    <p className="text-sm flex-1 text-white/80">{step.description}</p>
                    <span className="agent-badge text-[11px]"
                      style={{ background: cfg.bg, color: cfg.color }}>
                      <Icon className="w-3 h-3" />
                      {cfg.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Steps */}
        {taskState.steps.map((step, idx) => {
          const key = step.agent === 'ReviewerAgent' ? 'review' : `${step.agent}-${step.step_number}-${idx}`;
          const cfg = AGENT_CONFIG[step.agent] || AGENT_CONFIG.ExecutorAgent;
          const Icon = cfg.icon;
          const isExpanded = expandedSteps.has(key);

          return (
            <div key={key} className="glass rounded-2xl overflow-hidden animate-slide-up">
              <button
                className="w-full flex items-center gap-3 p-4 text-left hover:bg-white/[0.02] transition-colors"
                onClick={() => toggleStep(key)}
              >
                <div className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: cfg.bg, border: `1px solid ${cfg.color}30` }}>
                  <Icon className="w-4 h-4" style={{ color: cfg.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-white">{cfg.label}</span>
                    {step.step_number < 999 && (
                      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Step {step.step_number}</span>
                    )}
                  </div>
                  <p className="text-xs truncate mt-0.5" style={{ color: 'var(--text-muted)' }}>
                    {step.input}
                  </p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  {step.duration_ms && (
                    <span className="text-xs flex items-center gap-1" style={{ color: 'var(--text-muted)' }}>
                      <Clock className="w-3 h-3" />
                      {formatMs(step.duration_ms)}
                    </span>
                  )}
                  {step.status === 'success'
                    ? <CheckCircle className="w-4 h-4" style={{ color: '#22c55e' }} />
                    : <XCircle className="w-4 h-4" style={{ color: '#ef4444' }} />
                  }
                  {isExpanded
                    ? <ChevronDown className="w-4 h-4 text-white/40" />
                    : <ChevronRight className="w-4 h-4 text-white/40" />
                  }
                </div>
              </button>

              {isExpanded && (
                <div className="px-4 pb-4 border-t" style={{ borderColor: 'var(--border)' }}>
                  <div className="mt-4 p-4 rounded-xl prose-custom overflow-auto"
                    style={{ background: 'rgba(0,0,0,0.3)', maxHeight: '400px' }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {step.output || step.error || '(no output)'}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* Running indicator */}
        {taskState.status === 'running' && (
          <div className="flex items-center gap-3 px-5 py-4 rounded-2xl animate-fade-in"
            style={{ background: 'rgba(90,126,255,0.08)', border: '1px solid rgba(90,126,255,0.2)' }}>
            <Loader2 className="w-5 h-5 animate-spin" style={{ color: '#5a7eff' }} />
            <p className="text-sm" style={{ color: '#93c5fd' }}>
              Agents are working on your task...
            </p>
          </div>
        )}

        {/* Result */}
        {taskState.status === 'complete' && (
          <div className="glass rounded-2xl p-5 animate-slide-up"
            style={{ border: '1px solid rgba(34,197,94,0.3)', background: 'rgba(34,197,94,0.03)' }}>
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle className="w-5 h-5" style={{ color: '#22c55e' }} />
              <h3 className="text-sm font-semibold" style={{ color: '#86efac' }}>
                Task Complete · {formatMs(taskState.totalDuration)}
              </h3>
            </div>
            <div className="prose-custom"
              style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '12px', padding: '1rem' }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {taskState.finalOutput}
              </ReactMarkdown>
            </div>
          </div>
        )}

        {taskState.status === 'error' && (
          <div className="glass rounded-2xl p-5 animate-fade-in"
            style={{ border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.05)' }}>
            <div className="flex items-center gap-2 mb-2">
              <XCircle className="w-5 h-5" style={{ color: '#ef4444' }} />
              <h3 className="text-sm font-semibold" style={{ color: '#fca5a5' }}>Task Failed</h3>
            </div>
            <p className="text-sm" style={{ color: '#fca5a5' }}>{taskState.finalOutput}</p>
          </div>
        )}

        <div ref={stepsEndRef} />
      </div>
    </div>
  );
}
