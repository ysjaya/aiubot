import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './App.css';

const API_URL = import.meta.env.VITE_API_URL || '';

// Code Canvas Modal Component
function CodeCanvas({ code, language, filename, onClose }) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const downloadFile = () => {
    const blob = new Blob([code], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || `code.${language || 'txt'}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="code-canvas-overlay" onClick={onClose}>
      <div className="code-canvas" onClick={(e) => e.stopPropagation()}>
        <div className="code-canvas-header">
          <h3>{filename || `Code (${language || 'text'})`}</h3>
          <div className="code-canvas-actions">
            <button className="btn-icon" onClick={copyToClipboard} title="Copy">
              {copied ? '✅' : '📋'}
            </button>
            <button className="btn-icon" onClick={downloadFile} title="Download">
              ⬇️
            </button>
            <button className="btn-icon" onClick={onClose} title="Close">
              ✕
            </button>
          </div>
        </div>
        <div className="code-canvas-content">
          <SyntaxHighlighter
            style={vscDarkPlus}
            language={language || 'text'}
            PreTag="div"
            showLineNumbers
            wrapLongLines
          >
            {code}
          </SyntaxHighlighter>
        </div>
      </div>
    </div>
  );
}

// Typewriter Component for streaming text line-by-line
function TypewriterText({ text, speed = 30 }) {
  const [displayText, setDisplayText] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    if (currentIndex < text.length) {
      const timeout = setTimeout(() => {
        setDisplayText(prev => prev + text[currentIndex]);
        setCurrentIndex(prev => prev + 1);
      }, speed);
      return () => clearTimeout(timeout);
    }
  }, [currentIndex, text, speed]);

  useEffect(() => {
    setDisplayText('');
    setCurrentIndex(0);
  }, [text]);

  return <div className="typewriter">{displayText}</div>;
}

function App() {
  // State management
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [selectedConv, setSelectedConv] = useState(null);
  const [chats, setChats] = useState([]);
  const [attachments, setAttachments] = useState([]);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamingResponse, setStreamingResponse] = useState('');
  const [streamingLines, setStreamingLines] = useState([]);
  
  // UI state
  const [showNewProject, setShowNewProject] = useState(false);
  const [showNewConv, setShowNewConv] = useState(false);
  const [showFileManager, setShowFileManager] = useState(false);
  const [showGitHubImport, setShowGitHubImport] = useState(false);
  const [showAttachmentMenu, setShowAttachmentMenu] = useState(false);
  const [showCommitModal, setShowCommitModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newConvTitle, setNewConvTitle] = useState('');
  const [codeCanvas, setCodeCanvas] = useState(null);
  
  // GitHub state
  const [githubRepos, setGithubRepos] = useState([]);
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [repoFiles, setRepoFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [importProgress, setImportProgress] = useState(null);
  const [githubToken, setGithubToken] = useState(localStorage.getItem('github_token'));
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [loadingFiles, setLoadingFiles] = useState(false);
  
  // Commit state
  const [commitRepoName, setCommitRepoName] = useState('');
  const [commitBranch, setCommitBranch] = useState('main');
  const [commitMessage, setCommitMessage] = useState('');
  const [commitBasePath, setCommitBasePath] = useState('');
  const [committing, setCommitting] = useState(false);
  
  // Refs
  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chats, streamingLines]);

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  // Check for GitHub auth token in URL
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    if (token) {
      setGithubToken(token);
      localStorage.setItem('github_token', token);
      window.history.replaceState({}, document.title, window.location.pathname);
      alert('✅ GitHub terhubung!');
    }
  }, []);

  // Load conversations when project selected
  useEffect(() => {
    if (selectedProject) {
      loadConversations(selectedProject.id);
    }
  }, [selectedProject]);

  // Load chats and attachments when conversation selected
  useEffect(() => {
    if (selectedConv && selectedProject) {
      loadChats(selectedConv.id);
      loadAttachments(selectedConv.id);
    }
  }, [selectedConv, selectedProject]);

  // ==================== API CALLS ====================

  const loadProjects = async () => {
    try {
      const res = await fetch(`${API_URL}/api/projects`);
      const data = await res.json();
      setProjects(data);
    } catch (err) {
      console.error('Failed to load projects:', err);
    }
  };

  const createProject = async () => {
    if (!newProjectName.trim()) return;
    try {
      const res = await fetch(`${API_URL}/api/project?name=${encodeURIComponent(newProjectName)}`, {
        method: 'POST'
      });
      const project = await res.json();
      setProjects([project, ...projects]);
      setSelectedProject(project);
      setNewProjectName('');
      setShowNewProject(false);
    } catch (err) {
      console.error('Failed to create project:', err);
      alert('Gagal membuat project');
    }
  };

  const deleteProject = async (projectId) => {
    if (!confirm('Hapus project ini? Semua percakapan dan file akan terhapus!')) return;
    try {
      await fetch(`${API_URL}/api/project/${projectId}`, { method: 'DELETE' });
      setProjects(projects.filter(p => p.id !== projectId));
      if (selectedProject?.id === projectId) {
        setSelectedProject(null);
        setConversations([]);
        setSelectedConv(null);
      }
    } catch (err) {
      console.error('Failed to delete project:', err);
      alert('Gagal menghapus project');
    }
  };

  const loadConversations = async (projectId) => {
    try {
      const res = await fetch(`${API_URL}/api/project/${projectId}/conversations`);
      const data = await res.json();
      setConversations(data);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  };

  const createConversation = async () => {
    if (!newConvTitle.trim() || !selectedProject) return;
    try {
      const res = await fetch(
        `${API_URL}/api/conversation?project_id=${selectedProject.id}&title=${encodeURIComponent(newConvTitle)}`,
        { method: 'POST' }
      );
      const conv = await res.json();
      setConversations([conv, ...conversations]);
      setSelectedConv(conv);
      setNewConvTitle('');
      setShowNewConv(false);
    } catch (err) {
      console.error('Failed to create conversation:', err);
      alert('Gagal membuat percakapan');
    }
  };

  const deleteConversation = async (convId) => {
    if (!confirm('Hapus percakapan ini?')) return;
    try {
      await fetch(`${API_URL}/api/conversation/${convId}?project_id=${selectedProject.id}`, {
        method: 'DELETE'
      });
      setConversations(conversations.filter(c => c.id !== convId));
      if (selectedConv?.id === convId) {
        setSelectedConv(null);
        setChats([]);
        setAttachments([]);
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      alert('Gagal menghapus percakapan');
    }
  };

  const loadChats = async (convId) => {
    try {
      const res = await fetch(`${API_URL}/api/conversation/${convId}/chats?project_id=${selectedProject.id}`);
      const data = await res.json();
      setChats(data);
    } catch (err) {
      console.error('Failed to load chats:', err);
    }
  };

  const loadAttachments = async (convId) => {
    try {
      const res = await fetch(`${API_URL}/api/conversation/${convId}/attachments?project_id=${selectedProject.id}`);
      const data = await res.json();
      setAttachments(data);
    } catch (err) {
      console.error('Failed to load attachments:', err);
    }
  };

  const uploadFile = async (file) => {
    if (!selectedConv || !selectedProject) {
      alert('Pilih percakapan terlebih dahulu');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(
        `${API_URL}/api/conversation/${selectedConv.id}/attach?project_id=${selectedProject.id}`,
        {
          method: 'POST',
          body: formData
        }
      );
      
      if (!res.ok) throw new Error('Upload failed');
      
      const attachment = await res.json();
      setAttachments([attachment, ...attachments]);
      alert(`✅ File terupload: ${attachment.filename}`);
    } catch (err) {
      console.error('Failed to upload file:', err);
      alert('Gagal upload file. Pastikan file teks dan di bawah 1MB.');
    }
  };

  const deleteAttachment = async (fileId) => {
    if (!confirm('Hapus file ini dan semua versinya?')) return;
    
    try {
      await fetch(`${API_URL}/api/attachment/${fileId}?project_id=${selectedProject.id}`, {
        method: 'DELETE'
      });
      setAttachments(attachments.filter(a => a.id !== fileId));
      alert('✅ File terhapus');
    } catch (err) {
      console.error('Failed to delete attachment:', err);
      alert('Gagal menghapus file');
    }
  };

  const downloadFile = async (fileId, filename) => {
    try {
      const res = await fetch(`${API_URL}/api/attachment/${fileId}/download?project_id=${selectedProject.id}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download file:', err);
      alert('Gagal download file');
    }
  };

  const sendMessage = async () => {
    if (!message.trim() || !selectedConv || !selectedProject || loading) return;

    const userMessage = message;
    setMessage('');
    setLoading(true);
    setStreamingResponse('');
    setStreamingLines([]);

    const tempChat = {
      id: Date.now(),
      user: 'user',
      message: userMessage,
      ai_response: '...',
      created_at: new Date().toISOString()
    };
    setChats([...chats, tempChat]);

    try {
      const res = await fetch(`${API_URL}/api/chat/${selectedConv.id}?project_id=${selectedProject.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage })
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let fullResponse = '';
      let currentLine = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            
            try {
              const parsed = JSON.parse(data);
              if (parsed.status === 'update') {
                setStreamingResponse(`_${parsed.message}_\n\n`);
              } else if (parsed.status === 'done') {
                break;
              } else if (parsed.status === 'error') {
                alert(`Error: ${parsed.message}`);
              }
            } catch {
              // Process text line by line for typewriter effect
              for (const char of data) {
                if (char === '\n') {
                  if (currentLine.trim()) {
                    setStreamingLines(prev => [...prev, currentLine]);
                    currentLine = '';
                    await new Promise(resolve => setTimeout(resolve, 50)); // Delay between lines
                  }
                } else {
                  currentLine += char;
                }
              }
              fullResponse += data;
              setStreamingResponse(fullResponse);
            }
          }
        }
      }

      // Add remaining line if any
      if (currentLine.trim()) {
        setStreamingLines(prev => [...prev, currentLine]);
      }

      await loadChats(selectedConv.id);
      await loadAttachments(selectedConv.id);
      setStreamingResponse('');
      setStreamingLines([]);

    } catch (err) {
      console.error('Failed to send message:', err);
      alert('Gagal mengirim pesan');
      setChats(chats);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    files.forEach(file => uploadFile(file));
    e.target.value = '';
  };

  // ==================== GITHUB FUNCTIONS ====================

  const handleGitHubAuth = () => {
    window.location.href = `${API_URL}/api/auth/login`;
  };

  const handleGitHubLogout = () => {
    setGithubToken(null);
    localStorage.removeItem('github_token');
    alert('Logout dari GitHub');
  };

  const loadGitHubRepos = async () => {
    if (!githubToken) {
      alert('Silakan login GitHub terlebih dahulu');
      return;
    }

    setLoadingRepos(true);
    try {
      const res = await fetch(`${API_URL}/api/github/repos`, {
        headers: { 'Authorization': `Bearer ${githubToken}` }
      });
      
      if (!res.ok) {
        throw new Error('Failed to load repositories');
      }
      
      const data = await res.json();
      setGithubRepos(data.repos || []);
    } catch (err) {
      console.error('Failed to load GitHub repos:', err);
      alert('Gagal memuat repository. Silakan login ulang.');
      handleGitHubLogout();
    } finally {
      setLoadingRepos(false);
    }
  };

  const selectRepo = async (repo) => {
    setSelectedRepo(repo);
    setLoadingFiles(true);
    setRepoFiles([]);
    setSelectedFiles(new Set());
    
    try {
      const [owner, name] = repo.full_name.split('/');
      const res = await fetch(`${API_URL}/api/github/repo/${owner}/${name}/files`, {
        headers: { 'Authorization': `Bearer ${githubToken}` }
      });
      
      if (!res.ok) {
        throw new Error('Failed to load repository files');
      }
      
      const data = await res.json();
      setRepoFiles(data.importable || []);
    } catch (err) {
      console.error('Failed to load repo files:', err);
      alert('Gagal memuat file repository');
      setSelectedRepo(null);
    } finally {
      setLoadingFiles(false);
    }
  };

  const toggleFileSelection = (filePath) => {
    const newSelection = new Set(selectedFiles);
    if (newSelection.has(filePath)) {
      newSelection.delete(filePath);
    } else {
      newSelection.add(filePath);
    }
    setSelectedFiles(newSelection);
  };

  const selectAllFiles = () => {
    setSelectedFiles(new Set(repoFiles.map(f => f.path)));
  };

  const deselectAllFiles = () => {
    setSelectedFiles(new Set());
  };

  const importSelectedFiles = async () => {
    if (selectedFiles.size === 0) {
      alert('Pilih file untuk diimport');
      return;
    }

    if (!selectedConv || !selectedProject) {
      alert('Pilih percakapan terlebih dahulu');
      return;
    }

    setImportProgress({ current: 0, total: selectedFiles.size });

    try {
      const res = await fetch(`${API_URL}/api/github/import`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${githubToken}`
        },
        body: JSON.stringify({
          repo_fullname: selectedRepo.full_name,
          file_paths: Array.from(selectedFiles),
          conversation_id: selectedConv.id,
          project_id: selectedProject.id
        })
      });

      if (!res.ok) {
        throw new Error('Import failed');
      }

      const data = await res.json();
      
      if (data.success) {
        alert(`✅ Berhasil import ${data.imported_count} file!`);
        await loadAttachments(selectedConv.id);
        setShowGitHubImport(false);
        setSelectedRepo(null);
        setRepoFiles([]);
        setSelectedFiles(new Set());
      }
    } catch (err) {
      console.error('Failed to import files:', err);
      alert('Gagal import file: ' + err.message);
    } finally {
      setImportProgress(null);
    }
  };

  const openGitHubImportModal = () => {
    if (!selectedConv) {
      alert('Pilih percakapan terlebih dahulu');
      return;
    }
    
    setShowGitHubImport(true);
    
    // Auto-load repos if already authenticated
    if (githubToken && githubRepos.length === 0) {
      loadGitHubRepos();
    }
  };

  const closeGitHubImportModal = () => {
    setShowGitHubImport(false);
    setSelectedRepo(null);
    setRepoFiles([]);
    setSelectedFiles(new Set());
    setImportProgress(null);
  };

  // ==================== COMMIT FUNCTIONS ====================

  const openCommitModal = () => {
    if (!selectedConv) {
      alert('Pilih percakapan terlebih dahulu');
      return;
    }
    
    if (attachments.length === 0) {
      alert('Tidak ada file untuk di-commit');
      return;
    }
    
    if (!githubToken) {
      alert('Silakan login GitHub terlebih dahulu');
      handleGitHubAuth();
      return;
    }
    
    setShowCommitModal(true);
    setCommitMessage(`Update ${attachments.length} file(s) from AI Code Assistant`);
    
    // Auto-load repos if needed
    if (githubRepos.length === 0) {
      loadGitHubRepos();
    }
  };

  const closeCommitModal = () => {
    setShowCommitModal(false);
    setCommitRepoName('');
    setCommitBranch('main');
    setCommitMessage('');
    setCommitBasePath('');
  };

  const commitAllFiles = async () => {
    if (!commitRepoName) {
      alert('Pilih repository untuk commit');
      return;
    }

    setCommitting(true);
    
    try {
      const res = await fetch(`${API_URL}/api/github/commit-all`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${githubToken}`
        },
        body: JSON.stringify({
          repo_fullname: commitRepoName,
          conversation_id: selectedConv.id,
          project_id: selectedProject.id,
          branch: commitBranch || 'main',
          commit_message: commitMessage,
          base_path: commitBasePath
        })
      });

      if (!res.ok) {
        throw new Error('Commit failed');
      }

      const data = await res.json();

      if (data.success) {
        alert(`✅ Berhasil commit ${data.files_count} file ke ${commitRepoName}!\n\nCommit: ${data.commit_sha.substring(0, 7)}\nBranch: ${data.branch}\n\nURL: ${data.commit_url}`);
        
        // Open commit URL
        if (confirm('Buka commit di GitHub?')) {
          window.open(data.commit_url, '_blank');
        }
        
        closeCommitModal();
      }
    } catch (err) {
      console.error('Failed to commit files:', err);
      alert('Gagal commit file: ' + err.message);
    } finally {
      setCommitting(false);
    }
  };

  // ==================== RENDER HELPERS ====================

  const renderFileStatus = (att) => {
    const statusMap = {
      'original': '📄 Original',
      'modified': '✏️ Modified',
      'latest': '✨ Latest'
    };
    return statusMap[att.status] || '📄';
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Custom Code Block Renderer dengan link ke canvas
  const CodeBlock = ({ language, value }) => {
    const filename = `code.${language || 'txt'}`;
    return (
      <div className="code-block-wrapper">
        <div className="code-block-header">
          <span className="code-language">{language || 'text'}</span>
          <button
            className="code-view-button"
            onClick={() => setCodeCanvas({ code: value, language, filename })}
          >
            📝 Lihat di Canvas →
          </button>
        </div>
        <div className="code-preview">
          <code>{value.split('\n').slice(0, 3).join('\n')}...</code>
        </div>
      </div>
    );
  };

  // ==================== JSX RENDER ====================

  return (
    <div className="app">
      {/* SIDEBAR */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h2>🤖 AI Code</h2>
          <button className="btn-icon" onClick={() => setShowFileManager(!showFileManager)}>
            📁
          </button>
        </div>

        {/* PROJECTS */}
        <div className="sidebar-section">
          <div className="section-header">
            <h3>Projects</h3>
            <button className="btn-icon" onClick={() => setShowNewProject(!showNewProject)}>
              +
            </button>
          </div>

          {showNewProject && (
            <div className="new-item-form">
              <input
                type="text"
                placeholder="Nama project..."
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && createProject()}
              />
              <div className="form-actions">
                <button className="btn-secondary" onClick={() => setShowNewProject(false)}>
                  Batal
                </button>
                <button className="btn-primary" onClick={createProject}>
                  Buat
                </button>
              </div>
            </div>
          )}

          <div className="projects-list">
            {projects.map(p => (
              <div
                key={p.id}
                className={`project-item ${selectedProject?.id === p.id ? 'active' : ''}`}
                onClick={() => setSelectedProject(p)}
              >
                <div>
                  <strong>{p.name}</strong>
                  <small>{new Date(p.created_at).toLocaleDateString('id-ID')}</small>
                </div>
                <button
                  className="btn-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteProject(p.id);
                  }}
                >
                  🗑️
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* CONVERSATIONS */}
        <div className="sidebar-section">
          <div className="section-header">
            <h3>Percakapan</h3>
            <button
              className="btn-icon"
              onClick={() => setShowNewConv(!showNewConv)}
              disabled={!selectedProject}
            >
              +
            </button>
          </div>

          {showNewConv && (
            <div className="new-item-form">
              <input
                type="text"
                placeholder="Judul percakapan..."
                value={newConvTitle}
                onChange={(e) => setNewConvTitle(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && createConversation()}
              />
              <div className="form-actions">
                <button className="btn-secondary" onClick={() => setShowNewConv(false)}>
                  Batal
                </button>
                <button className="btn-primary" onClick={createConversation}>
                  Buat
                </button>
              </div>
            </div>
          )}

          <div className="conversations-list">
            {conversations.map(c => (
              <div
                key={c.id}
                className={`conversation-item ${selectedConv?.id === c.id ? 'active' : ''}`}
                onClick={() => setSelectedConv(c)}
              >
                <div>
                  <strong>{c.title}</strong>
                  <small>{new Date(c.created_at).toLocaleDateString('id-ID')}</small>
                </div>
                <button
                  className="btn-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(c.id);
                  }}
                >
                  🗑️
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div className="main-content">
        {!selectedConv ? (
          <div className="empty-state">
            <h2>Selamat Datang di AI Code Assistant</h2>
            <p>Pilih atau buat project dan percakapan untuk mulai</p>
            <div className="features">
              <div className="feature">
                <span>📁</span>
                <h3>Manajemen Project</h3>
                <p>Atur kode Anda berdasarkan project</p>
              </div>
              <div className="feature">
                <span>💬</span>
                <h3>AI Chat</h3>
                <p>Dapatkan bantuan kode dari AI</p>
              </div>
              <div className="feature">
                <span>📝</span>
                <h3>Versioning File</h3>
                <p>Lacak perubahan file otomatis</p>
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* CHAT HEADER */}
            <div className="chat-header">
              <div>
                <h2>{selectedConv.title}</h2>
                <small>{selectedProject.name}</small>
              </div>
            </div>

            {/* FILE MANAGER */}
            {showFileManager && (
              <div className="file-manager">
                <div className="file-manager-header">
                  <h3>File Terlampir ({attachments.length})</h3>
                  <button onClick={() => setShowFileManager(false)}>✕</button>
                </div>
                <div className="file-list">
                  {attachments.length === 0 ? (
                    <div className="empty-files">Belum ada file</div>
                  ) : (
                    attachments.map(att => (
                      <div key={att.id} className="file-item">
                        <div className="file-info">
                          <span className="file-status">{renderFileStatus(att)}</span>
                          <div className="file-details">
                            <strong>{att.filename}</strong>
                            <small>
                              v{att.version} • {formatFileSize(att.size_bytes)}
                            </small>
                          </div>
                        </div>
                        <div className="file-actions">
                          <button
                            className="btn-icon"
                            onClick={() => downloadFile(att.id, att.filename)}
                            title="Download"
                          >
                            ⬇️
                          </button>
                          <button
                            className="btn-delete"
                            onClick={() => deleteAttachment(att.id)}
                            title="Hapus"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* CHAT MESSAGES */}
            <div className="chat-messages">
              {chats.map((chat) => (
                <div key={chat.id} className="chat-bubble-container">
                  <div className="chat-bubble user">
                    <strong>Anda</strong>
                    <ReactMarkdown>{chat.message}</ReactMarkdown>
                  </div>
                  <div className="chat-bubble ai">
                    <strong>AI Assistant</strong>
                    <ReactMarkdown
                      components={{
                        code({node, inline, className, children, ...props}) {
                          const match = /language-(\w+)/.exec(className || '');
                          const value = String(children).replace(/\n$/, '');
                          
                          if (!inline && match) {
                            return <CodeBlock language={match[1]} value={value} />;
                          }
                          
                          return (
                            <code className={className} {...props}>
                              {children}
                            </code>
                          );
                        }
                      }}
                    >
                      {chat.ai_response}
                    </ReactMarkdown>
                  </div>
                </div>
              ))}

              {/* Streaming response dengan typewriter effect */}
              {streamingLines.length > 0 && (
                <div className="chat-bubble-container">
                  <div className="chat-bubble ai streaming">
                    <strong>AI Assistant</strong>
                    {streamingLines.map((line, idx) => (
                      <TypewriterText key={idx} text={line} speed={20} />
                    ))}
                  </div>
                </div>
              )}

              {streamingResponse && streamingLines.length === 0 && (
                <div className="chat-bubble-container">
                  <div className="chat-bubble ai streaming">
                    <strong>AI Assistant</strong>
                    <ReactMarkdown>{streamingResponse}</ReactMarkdown>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            {/* CHAT INPUT */}
            <div className="chat-input-container">
              <div className="chat-input-actions">
                <button
                  className="btn-commit"
                  onClick={openCommitModal}
                  disabled={loading || attachments.length === 0}
                  title="Commit all files to GitHub"
                >
                  🚀 Commit to GitHub
                </button>
              </div>
              <div className="chat-input">
                <input
                  type="file"
                  ref={fileInputRef}
                  style={{ display: 'none' }}
                  onChange={handleFileSelect}
                  accept=".txt,.py,.js,.jsx,.ts,.tsx,.json,.md,.html,.css,.java,.c,.cpp,.go,.rs"
                />
                <div className="attachment-dropdown">
                  <button
                    className="btn-secondary btn-attachment"
                    onClick={() => setShowAttachmentMenu(!showAttachmentMenu)}
                    disabled={loading}
                  >
                    📎
                  </button>
                  {showAttachmentMenu && (
                    <div className="dropdown-menu">
                      <button
                        className="dropdown-item"
                        onClick={() => {
                          setShowAttachmentMenu(false);
                          openGitHubImportModal();
                        }}
                      >
                        📦 Import from GitHub
                      </button>
                      <button
                        className="dropdown-item"
                        onClick={() => {
                          setShowAttachmentMenu(false);
                          fileInputRef.current?.click();
                        }}
                      >
                        💻 Upload from Local
                      </button>
                    </div>
                  )}
                </div>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                  placeholder="Tanya apa saja tentang kode Anda..."
                  disabled={loading}
                  rows={3}
                />
                <button
                  className="btn-send"
                  onClick={sendMessage}
                  disabled={loading || !message.trim()}
                >
                  {loading ? '⏳' : '📤'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* CODE CANVAS MODAL */}
      {codeCanvas && (
        <CodeCanvas
          code={codeCanvas.code}
          language={codeCanvas.language}
          filename={codeCanvas.filename}
          onClose={() => setCodeCanvas(null)}
        />
      )}

      {/* COMMIT MODAL */}
      {showCommitModal && (
        <div className="modal-overlay" onClick={closeCommitModal}>
          <div className="modal-content commit-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>🚀 Commit All Files to GitHub</h2>
              <button className="btn-close" onClick={closeCommitModal}>
                ✕
              </button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label>Repository *</label>
                <select
                  value={commitRepoName}
                  onChange={(e) => setCommitRepoName(e.target.value)}
                  disabled={committing}
                >
                  <option value="">-- Pilih Repository --</option>
                  {githubRepos.map(repo => (
                    <option key={repo.full_name} value={repo.full_name}>
                      {repo.full_name} {repo.private ? '🔒' : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Branch</label>
                <input
                  type="text"
                  value={commitBranch}
                  onChange={(e) => setCommitBranch(e.target.value)}
                  placeholder="main"
                  disabled={committing}
                />
                <small>Branch akan dibuat otomatis jika belum ada</small>
              </div>

              <div className="form-group">
                <label>Commit Message *</label>
                <textarea
                  value={commitMessage}
                  onChange={(e) => setCommitMessage(e.target.value)}
                  placeholder="Update files from AI Code Assistant"
                  rows={3}
                  disabled={committing}
                />
              </div>

              <div className="form-group">
                <label>Base Path (Optional)</label>
                <input
                  type="text"
                  value={commitBasePath}
                  onChange={(e) => setCommitBasePath(e.target.value)}
                  placeholder="e.g., src/ or backend/"
                  disabled={committing}
                />
                <small>Folder tujuan di repository (kosongkan untuk root)</small>
              </div>

              <div className="commit-summary">
                <strong>📊 Summary:</strong>
                <p>{attachments.filter(a => a.status === 'latest').length} files will be committed</p>
              </div>

              <div className="modal-footer">
                <button
                  className="btn-secondary"
                  onClick={closeCommitModal}
                  disabled={committing}
                >
                  Batal
                </button>
                <button
                  className="btn-primary btn-large"
                  onClick={commitAllFiles}
                  disabled={committing || !commitRepoName || !commitMessage}
                >
                  {committing ? '⏳ Committing...' : '🚀 Commit Now'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* GITHUB IMPORT MODAL */}
      {showGitHubImport && (
        <div className="modal-overlay" onClick={closeGitHubImportModal}>
          <div className="modal-content github-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>📦 Import dari GitHub</h2>
              <button className="btn-close" onClick={closeGitHubImportModal}>
                ✕
              </button>
            </div>

            <div className="modal-body">
              {!githubToken ? (
                <div className="auth-prompt">
                  <p>Hubungkan akun GitHub Anda untuk import repository</p>
                  <button className="btn-primary btn-large" onClick={handleGitHubAuth}>
                    🔐 Hubungkan GitHub
                  </button>
                </div>
              ) : !selectedRepo ? (
                <>
                  <div className="repo-header">
                    <h3>Repository Anda</h3>
                    <div className="repo-actions">
                      <button className="btn-secondary" onClick={loadGitHubRepos} disabled={loadingRepos}>
                        {loadingRepos ? '⏳' : '🔄'}
                      </button>
                      <button className="btn-secondary" onClick={handleGitHubLogout}>
                        🚪
                      </button>
                    </div>
                  </div>

                  {loadingRepos ? (
                    <div className="loading-state">
                      <div className="spinner">⏳</div>
                      <p>Memuat repository...</p>
                    </div>
                  ) : githubRepos.length === 0 ? (
                    <div className="empty-state-small">
                      <p>Belum ada repository</p>
                      <button className="btn-primary" onClick={loadGitHubRepos}>
                        Muat Repository
                      </button>
                    </div>
                  ) : (
                    <div className="github-repos-list">
                      {githubRepos.map((repo) => (
                        <div key={repo.full_name} className="github-repo-item">
                          <div className="repo-info">
                            <strong>{repo.name}</strong>
                            <small>{repo.description || 'Tidak ada deskripsi'}</small>
                            <div className="repo-meta">
                              {repo.language && (
                                <span className="repo-lang">{repo.language}</span>
                              )}
                              <span>⭐ {repo.stars}</span>
                              {repo.private && <span className="repo-private">🔒</span>}
                            </div>
                          </div>
                          <button
                            className="btn-primary"
                            onClick={() => selectRepo(repo)}
                          >
                            Pilih →
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div className="repo-selected-header">
                    <button className="btn-back" onClick={() => {
                      setSelectedRepo(null);
                      setRepoFiles([]);
                      setSelectedFiles(new Set());
                    }}>
                      ← Kembali
                    </button>
                    <h3>{selectedRepo.name}</h3>
                  </div>

                  {loadingFiles ? (
                    <div className="loading-state">
                      <div className="spinner">⏳</div>
                      <p>Memuat file...</p>
                    </div>
                  ) : repoFiles.length === 0 ? (
                    <div className="empty-state-small">
                      <p>Tidak ada file yang bisa diimport</p>
                    </div>
                  ) : (
                    <>
                      <div className="file-selection-actions">
                        <button className="btn-secondary" onClick={selectAllFiles}>
                          Pilih Semua
                        </button>
                        <button className="btn-secondary" onClick={deselectAllFiles}>
                          Batal Pilih
                        </button>
                        <span className="selection-count">
                          {selectedFiles.size} / {repoFiles.length}
                        </span>
                      </div>

                      {importProgress && (
                        <div className="import-progress">
                          <p>Mengimport file...</p>
                          <div className="progress-bar">
                            <div 
                              className="progress-fill" 
                              style={{ width: `${(importProgress.current / importProgress.total) * 100}%` }}
                            />
                          </div>
                        </div>
                      )}

                      <div className="github-files-list">
                        {repoFiles.map((file) => (
                          <div
                            key={file.path}
                            className={`github-file-item ${selectedFiles.has(file.path) ? 'selected' : ''}`}
                            onClick={() => toggleFileSelection(file.path)}
                          >
                            <input
                              type="checkbox"
                              checked={selectedFiles.has(file.path)}
                              onChange={() => toggleFileSelection(file.path)}
                            />
                            <div className="file-info">
                              <strong>{file.path.split('/').pop()}</strong>
                              <small>{file.path}</small>
                            </div>
                            <span className="file-size">{formatFileSize(file.size)}</span>
                          </div>
                        ))}
                      </div>

                      <div className="modal-footer">
                        <button
                          className="btn-primary btn-large"
                          onClick={importSelectedFiles}
                          disabled={selectedFiles.size === 0 || importProgress}
                        >
                          Import {selectedFiles.size} File
                        </button>
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
