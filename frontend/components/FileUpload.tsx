'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, CheckCircle, XCircle, Loader2, Trash2, Database } from 'lucide-react';
import clsx from 'clsx';

interface UploadedFile {
  id: string;
  filename: string;
  status: 'uploading' | 'success' | 'error';
  chunks?: number;
  pages?: number;
  message?: string;
  error?: string;
  size: number;
}

export default function FileUpload() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [namespace, setNamespace] = useState('default');
  const [isUploading, setIsUploading] = useState(false);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const pdfs = acceptedFiles.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (!pdfs.length) return;

    setIsUploading(true);

    for (const file of pdfs) {
      const tempId = crypto.randomUUID();

      // Add placeholder
      setFiles(prev => [...prev, {
        id: tempId,
        filename: file.name,
        status: 'uploading',
        size: file.size,
      }]);

      const formData = new FormData();
      formData.append('file', file);
      formData.append('namespace', namespace);

      try {
        const res = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        });

        const data = await res.json();

        if (!res.ok) {
          setFiles(prev => prev.map(f => f.id === tempId
            ? { ...f, id: tempId, status: 'error', error: data.detail || 'Upload failed' }
            : f
          ));
        } else {
          setFiles(prev => prev.map(f => f.id === tempId
            ? {
              ...f,
              id: data.file_id || tempId,
              status: 'success',
              chunks: data.chunks_created,
              pages: data.pages_processed,
              message: data.message,
            }
            : f
          ));
        }
      } catch (err: any) {
        setFiles(prev => prev.map(f => f.id === tempId
          ? { ...f, status: 'error', error: err.message }
          : f
        ));
      }
    }

    setIsUploading(false);
  }, [namespace]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: true,
    disabled: isUploading,
  });

  const removeFile = (id: string) => {
    setFiles(prev => prev.filter(f => f.id !== id));
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="h-full overflow-y-auto p-8" style={{ background: 'var(--bg-base)' }}>
      <div className="max-w-3xl mx-auto space-y-6">

        {/* Header */}
        <div className="animate-fade-in">
          <h1 className="text-2xl font-bold text-white mb-1">Document Upload</h1>
          <p style={{ color: 'var(--text-secondary)' }}>
            Upload PDFs to your knowledge base. Documents are chunked, embedded, and indexed for semantic search.
          </p>
        </div>

        {/* Stats Bar */}
        <div className="grid grid-cols-3 gap-4 animate-slide-up">
          {[
            { label: 'Files Uploaded', value: files.filter(f => f.status === 'success').length, color: '#22c55e' },
            { label: 'Total Chunks', value: files.reduce((s, f) => s + (f.chunks || 0), 0), color: '#5a7eff' },
            { label: 'Pages Processed', value: files.reduce((s, f) => s + (f.pages || 0), 0), color: '#9b6dff' },
          ].map(stat => (
            <div key={stat.label} className="glass rounded-xl p-4">
              <p className="text-2xl font-bold" style={{ color: stat.color }}>{stat.value}</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{stat.label}</p>
            </div>
          ))}
        </div>

        {/* Namespace Input */}
        <div className="glass rounded-xl p-4 flex items-center gap-4">
          <Database className="w-4 h-4 shrink-0" style={{ color: 'var(--text-muted)' }} />
          <div className="flex-1">
            <label className="text-xs font-medium text-white/60 block mb-1">Namespace / Collection</label>
            <input
              id="namespace-input"
              value={namespace}
              onChange={e => setNamespace(e.target.value.toLowerCase().replace(/\s+/g, '_'))}
              placeholder="default"
              className="input py-2 text-sm"
            />
          </div>
          <p className="text-xs max-w-[160px]" style={{ color: 'var(--text-muted)' }}>
            Group related documents together. Use in RAG queries.
          </p>
        </div>

        {/* Drop Zone */}
        <div
          {...getRootProps()}
          id="dropzone"
          className={clsx(
            'relative rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer transition-all duration-200',
            isDragActive
              ? 'border-blue-500 bg-blue-500/10'
              : 'border-white/10 hover:border-white/20 hover:bg-white/[0.02]',
            isUploading && 'pointer-events-none opacity-60'
          )}
        >
          <input {...getInputProps()} />

          <div className="flex flex-col items-center gap-4">
            <div className={clsx(
              'w-16 h-16 rounded-2xl flex items-center justify-center transition-transform duration-200',
              isDragActive ? 'scale-110' : ''
            )}
              style={{ background: isDragActive ? 'rgba(90,126,255,0.2)' : 'rgba(255,255,255,0.05)' }}>
              <Upload className={clsx('w-8 h-8', isDragActive ? 'text-blue-400' : 'text-white/30')} />
            </div>

            {isDragActive ? (
              <p className="text-blue-400 font-semibold">Drop your PDFs here!</p>
            ) : (
              <>
                <div>
                  <p className="text-white font-semibold mb-1">Drop PDFs here or click to browse</p>
                  <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                    Supports PDF files up to 50MB · Multiple files allowed
                  </p>
                </div>
                <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-muted)' }}>
                  <span className="px-2 py-1 rounded-md" style={{ background: 'rgba(255,255,255,0.05)' }}>PDF</span>
                  <span>Chunk size: 512 tokens</span>
                  <span>Overlap: 64 tokens</span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* File List */}
        {files.length > 0 && (
          <div className="space-y-3 animate-slide-up">
            <h3 className="text-sm font-semibold text-white/70">Upload History</h3>
            {files.map(file => (
              <div key={file.id}
                className="glass rounded-xl p-4 flex items-start gap-4 animate-fade-in"
              >
                {/* Status Icon */}
                <div className="shrink-0 mt-0.5">
                  {file.status === 'uploading' && (
                    <Loader2 className="w-5 h-5 animate-spin" style={{ color: '#5a7eff' }} />
                  )}
                  {file.status === 'success' && (
                    <CheckCircle className="w-5 h-5" style={{ color: '#22c55e' }} />
                  )}
                  {file.status === 'error' && (
                    <XCircle className="w-5 h-5" style={{ color: '#ef4444' }} />
                  )}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 shrink-0" style={{ color: 'var(--text-muted)' }} />
                    <p className="text-sm font-medium text-white truncate">{file.filename}</p>
                    <span className="text-xs shrink-0" style={{ color: 'var(--text-muted)' }}>
                      {formatSize(file.size)}
                    </span>
                  </div>

                  {file.status === 'uploading' && (
                    <div className="mt-2 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
                      <div className="h-full w-2/3 rounded-full animate-pulse"
                        style={{ background: 'linear-gradient(90deg, #5a7eff, #9b6dff)' }} />
                    </div>
                  )}

                  {file.status === 'success' && (
                    <div className="flex items-center gap-3 mt-1.5 text-xs" style={{ color: '#86efac' }}>
                      <span>✅ {file.chunks} chunks</span>
                      <span>·</span>
                      <span>{file.pages} pages</span>
                      <span>·</span>
                      <span className="truncate" style={{ color: 'var(--text-muted)' }}>
                        namespace: {namespace}
                      </span>
                    </div>
                  )}

                  {file.status === 'error' && (
                    <p className="text-xs mt-1" style={{ color: '#fca5a5' }}>
                      ❌ {file.error}
                    </p>
                  )}
                </div>

                <button
                  onClick={() => removeFile(file.id)}
                  className="shrink-0 p-1.5 rounded-lg hover:bg-white/10 transition-colors"
                  title="Remove"
                >
                  <Trash2 className="w-3.5 h-3.5" style={{ color: 'var(--text-muted)' }} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
