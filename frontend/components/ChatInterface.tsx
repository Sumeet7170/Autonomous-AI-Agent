'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Bot, User, BookOpen, Cpu, RotateCcw, ChevronDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import clsx from 'clsx';

type Mode = 'chat' | 'rag' | 'agent';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

interface ChatInterfaceProps {
  sessionId: string;
}

const MODE_CONFIG: Record<Mode, { label: string; icon: React.ElementType; color: string; placeholder: string }> = {
  chat:  { label: 'Chat',  icon: Bot,      color: '#5a7eff', placeholder: 'Ask me anything...' },
  rag:   { label: 'RAG',   icon: BookOpen, color: '#9b6dff', placeholder: 'Ask a question about your documents...' },
  agent: { label: 'Agent', icon: Cpu,      color: '#22c55e', placeholder: 'Describe a task for the AI agents...' },
};

export default function ChatInterface({ sessionId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '0',
      role: 'assistant',
      content: "👋 Hello! I'm your Autonomous AI System.\n\n**Available modes:**\n- **Chat** — General conversation with memory\n- **RAG** — Answer questions from your uploaded documents\n- **Agent** — Execute multi-step tasks with 4 specialized agents\n\nHow can I help you today?",
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [mode, setMode] = useState<Mode>('chat');
  const [namespace, setNamespace] = useState('default');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
    }
  }, [input]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    const aiMsgId = crypto.randomUUID();
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };

    setMessages(prev => [...prev, userMsg, aiMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsg.content,
          session_id: sessionId,
          mode,
          namespace,
        }),
      });

      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      if (!res.body) throw new Error('No response body');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullContent = '';

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
            if (event.type === 'token' && event.data) {
              fullContent += event.data;
              setMessages(prev =>
                prev.map(m => m.id === aiMsgId
                  ? { ...m, content: fullContent }
                  : m
                )
              );
            } else if (event.type === 'done' || event.type === 'complete') {
              if (event.final_output) {
                fullContent = event.final_output;
              }
            }
          } catch { /* ignore parse errors */ }
        }
      }

      setMessages(prev =>
        prev.map(m => m.id === aiMsgId
          ? { ...m, content: fullContent || m.content, isStreaming: false }
          : m
        )
      );
    } catch (err: any) {
      setMessages(prev =>
        prev.map(m => m.id === aiMsgId
          ? { ...m, content: `❌ Error: ${err.message}`, isStreaming: false }
          : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    fetch(`/api/chat/history/${sessionId}`, { method: 'DELETE' }).catch(() => {});
  };

  const ModeIcon = MODE_CONFIG[mode].icon;

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-base)' }}>

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b shrink-0"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: `${MODE_CONFIG[mode].color}20`, border: `1px solid ${MODE_CONFIG[mode].color}40` }}>
            <ModeIcon className="w-4 h-4" style={{ color: MODE_CONFIG[mode].color }} />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white">AI Chat</h2>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Mode: <span style={{ color: MODE_CONFIG[mode].color }}>{MODE_CONFIG[mode].label}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Mode Selector */}
          <div className="flex items-center gap-1 p-1 rounded-lg" style={{ background: 'var(--bg-card)' }}>
            {(Object.keys(MODE_CONFIG) as Mode[]).map(m => {
              const Icon = MODE_CONFIG[m].icon;
              return (
                <button
                  key={m}
                  id={`mode-${m}`}
                  onClick={() => setMode(m)}
                  className={clsx(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all',
                    mode === m
                      ? 'text-white'
                      : 'text-white/40 hover:text-white/70'
                  )}
                  style={mode === m ? {
                    background: `${MODE_CONFIG[m].color}20`,
                    color: MODE_CONFIG[m].color,
                  } : {}}
                >
                  <Icon className="w-3 h-3" />
                  {MODE_CONFIG[m].label}
                </button>
              );
            })}
          </div>

          {mode === 'rag' && (
            <input
              value={namespace}
              onChange={e => setNamespace(e.target.value)}
              placeholder="namespace"
              className="input text-xs w-28 py-1.5"
            />
          )}

          <button onClick={clearChat} className="btn-ghost p-2 rounded-lg" title="Clear chat">
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-6 px-6 space-y-4">
        {messages.map(msg => (
          <div
            key={msg.id}
            className={clsx(
              'flex gap-3 animate-fade-in',
              msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'
            )}
          >
            {/* Avatar */}
            <div className={clsx(
              'w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1',
              msg.role === 'user'
                ? 'bg-brand-600'
                : 'bg-surface-3'
            )}
              style={msg.role === 'assistant' ? { border: '1px solid var(--border)' } : {}}>
              {msg.role === 'user'
                ? <User className="w-4 h-4 text-white" />
                : <Bot className="w-4 h-4" style={{ color: '#5a7eff' }} />
              }
            </div>

            {/* Bubble */}
            <div className={msg.role === 'user' ? 'bubble-user' : 'bubble-ai'}>
              {msg.role === 'user' ? (
                <p className="text-sm leading-relaxed">{msg.content}</p>
              ) : (
                <div className="prose-custom">
                  {msg.isStreaming && !msg.content ? (
                    <div className="flex gap-1.5 items-center py-1">
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                    </div>
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  )}
                  {msg.isStreaming && msg.content && (
                    <span className="inline-block w-0.5 h-4 bg-blue-400 ml-0.5 animate-pulse" />
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 px-6 pb-6 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
        <div className="flex gap-3 items-end p-3 rounded-2xl"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          <textarea
            ref={textareaRef}
            id="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={MODE_CONFIG[mode].placeholder}
            rows={1}
            disabled={isLoading}
            className="flex-1 bg-transparent text-sm text-white placeholder-white/30 outline-none resize-none leading-relaxed"
            style={{ minHeight: '24px', maxHeight: '160px' }}
          />
          <button
            id="send-btn"
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            className="btn-primary !px-4 !py-2.5 shrink-0 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:transform-none"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-center text-[11px] mt-2" style={{ color: 'var(--text-muted)' }}>
          ↵ Send · Shift+↵ Newline · Mode: <strong style={{ color: MODE_CONFIG[mode].color }}>{MODE_CONFIG[mode].label}</strong>
        </p>
      </div>
    </div>
  );
}
