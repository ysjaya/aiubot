import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './App.css';

const API_URL = import.meta.env.VITE_API_URL || '';

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
  
  // UI state
  const [showNewProject, setShowNewProject] = useState(false);
  const [showNewConv, setShowNewConv] = useState(false);
  const [showFileManager, setShowFileManager] = useState(false);
  const [showGitHubImport, setShowGitHubImport] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newConvTitle, setNewConvTitle] = useState('');
  
  // GitHub state
  const [githubRepos, setGithubRepos] = useState([]);
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [repoFiles, setRepoFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [importProgress, setImportProgress] = useState(null);
  const [githubToken, setGithubToken] = useState(localStorage.getItem('github_token'));
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [loadingFiles, setLoadingFiles] = useState(false);
  
  // Refs
  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chats, streamingResponse]);

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
      alert('✅ Successfully authenticated with GitHub!');
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
      alert('Failed to create project');
    }
  };

  const deleteProject = async (projectId) => {
    if (!confirm('Delete this project? This will delete ALL conversations and files!')) return;
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
      alert('Failed to delete project');
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
      alert('Failed to create conversation');
    }
  };

  const deleteConversation = async (convId) => {
    if (!confirm('Delete this conversation?')) return;
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
      alert('Failed to delete conversation');
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
      alert('Please select a conversation first');
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
      alert(`✅ File uploaded: ${attachment.filename}`);
    } catch (err) {
      console.error('Failed to upload file:', err);
      alert('Failed to upload file. Make sure it is a text file under 1MB.');
    }
  };

  const deleteAttachment = async (fileId) => {
    if (!confirm('Delete this file and all its versions?')) return;
    
    try {
      await fetch(`${API_URL}/api/attachment/${fileId}?project_id=${selectedProject.id}`, {
        method: 'DELETE'
      });
      setAttachments(attachments.filter(a => a.id !== fileId));
      alert('✅ File deleted');
    } catch (err) {
      console.error('Failed to delete attachment:', err);
      alert('Failed to delete file');
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
      alert('Failed to download file');
    }
  };

  const sendMessage = async () => {
    if (!message.trim() || !selectedConv || !selectedProject || loading) return;

    const userMessage = message;
    setMessage('');
    setLoading(true);
    setStreamingResponse('');

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
              fullResponse += data;
              setStreamingResponse(fullResponse);
            }
          }
        }
      }

      await loadChats(selectedConv.id);
      await loadAttachments(selectedConv.id);
      setStreamingResponse('');

    } catch (err) {
      console.error('Failed to send message:', err);
      alert('Failed to send message');
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
    alert('Logged out from GitHub');
  };

  const loadGitHubRepos = async () => {
    if (!githubToken) {
      alert('Please authenticate with GitHub first');
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
      alert('Failed to load repositories. Please re-authenticate.');
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
      alert('Failed to load repository files');
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
      alert('Please select files to import');
      return;
    }

    if (!selectedConv || !selectedProject) {
      alert('Please select a conversation first');
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
        alert(`✅ Successfully imported ${data.imported_count} files!`);
        await loadAttachments(selectedConv.id);
        setShowGitHubImport(false);
        setSelectedRepo(null);
        setRepoFiles([]);
        setSelectedFiles(new Set());
      }
    } catch (err) {
      console.error('Failed to import files:', err);
      alert('Failed to import files: ' + err.message);
    } finally {
      setImportProgress(null);
    }
  };

  const openGitHubImportModal = () => {
    if (!selectedConv) {
      alert('Please select a conversation first');
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

  // ==================== JSX RENDER ====================

  return (
    <div className="app">
      {/* SIDEBAR */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h2>AI Code Assistant</h2>
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
                placeholder="Project name..."
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && createProject()}
              />
              <div className="form-actions">
                <button className="btn-secondary" onClick={() => setShowNewProject(false)}>
                  Cancel
                </button>
                <button className="btn-primary" onClick={createProject}>
                  Create
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
                  <small>{new Date(p.created_at).toLocaleDateString()}</small>
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
            <h3>Conversations</h3>
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
                placeholder="Conversation title..."
                value={newConvTitle}
                onChange={(e) => setNewConvTitle(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && createConversation()}
              />
              <div className="form-actions">
                <button className="btn-secondary" onClick={() => setShowNewConv(false)}>
                  Cancel
                </button>
                <button className="btn-primary" onClick={createConversation}>
                  Create
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
                  <small>{new Date(c.created_at).toLocaleDateString()}</small>
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
            <h2>Welcome to AI Code Assistant</h2>
            <p>Select or create a project and conversation to get started</p>
            <div className="features">
              <div className="feature">
                <span>📁</span>
                <h3>Project Management</h3>
                <p>Organize your code by projects with isolated databases</p>
              </div>
              <div className="feature">
                <span>💬</span>
                <h3>AI Chat</h3>
                <p>Get intelligent code assistance with context awareness</p>
              </div>
              <div className="feature">
                <span>📝</span>
                <h3>File Versioning</h3>
                <p>Track file changes with automatic versioning</p>
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
              <div className="header-actions">
                <button
                  className="btn-secondary"
                  onClick={openGitHubImportModal}
                  disabled={!selectedConv}
                >
                  📦 Import from GitHub
                </button>
              </div>
            </div>

            {/* FILE MANAGER */}
            {showFileManager && (
              <div className="file-manager">
                <div className="file-manager-header">
                  <h3>Attached Files ({attachments.length})</h3>
                  <button onClick={() => setShowFileManager(false)}>✕</button>
                </div>
                <div className="file-list">
                  {attachments.length === 0 ? (
                    <div className="empty-files">No files attached yet</div>
                  ) : (
                    attachments.map(att => (
                      <div key={att.id} className="file-item">
                        <div className="file-info">
                          <span className="file-status">{renderFileStatus(att)}</span>
                          <div className="file-details">
                            <strong>{att.filename}</strong>
                            <small>
                              v{att.version} • {formatFileSize(att.size_bytes)}
                              {att.modification_summary && ` • ${att.modification_summary}`}
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
                            title="Delete"
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
                    <strong>You</strong>
                    <ReactMarkdown>{chat.message}</ReactMarkdown>
                  </div>
                  <div className="chat-bubble ai">
                    <strong>AI Assistant</strong>
                    <ReactMarkdown
                      components={{
                        code({node, inline, className, children, ...props}) {
                          const match = /language-(\w+)/.exec(className || '');
                          return !inline && match ? (
                            <SyntaxHighlighter
                              style={vscDarkPlus}
                              language={match[1]}
                              PreTag="div"
                              {...props}
                            >
                              {String(children).replace(/\n$/, '')}
                            </SyntaxHighlighter>
                          ) : (
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

              {streamingResponse && (
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
              <div className="chat-input">
                <input
                  type="file"
                  ref={fileInputRef}
                  style={{ display: 'none' }}
                  onChange={handleFileSelect}
                  accept=".txt,.py,.js,.jsx,.ts,.tsx,.json,.md,.html,.css,.java,.c,.cpp,.go,.rs"
                />
                <button
                  className="btn-secondary"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={loading}
                >
                  📎
                </button>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                  placeholder="Ask anything about your code..."
                  disabled={loading}
                  rows={3}
                />
                <button
                  className="btn-send"
                  onClick={sendMessage}
                  disabled={loading || !message.trim()}
                >
                  {loading ? '⏳' : '📤'} Send
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* GITHUB IMPORT MODAL */}
      {showGitHubImport && (
        <div className="modal-overlay" onClick={closeGitHubImportModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>📦 Import from GitHub</h2>
              <button className="btn-close" onClick={closeGitHubImportModal}>
                ✕
              </button>
            </div>

            <div className="modal-body">
              {!githubToken ? (
                <div style={{ textAlign: 'center', padding: '40px' }}>
                  <p style={{ marginBottom: '20px', fontSize: '16px' }}>
                    Connect your GitHub account to import repositories
                  </p>
                  <button className="btn-primary" onClick={handleGitHubAuth} style={{ fontSize: '16px', padding: '12px 24px' }}>
                    🔐 Connect GitHub
                  </button>
                </div>
              ) : !selectedRepo ? (
                <>
                  <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3>Your Repositories</h3>
                    <div style={{ display: 'flex', gap: '10px' }}>
                      <button className="btn-secondary" onClick={loadGitHubRepos} disabled={loadingRepos}>
                        {loadingRepos ? '⏳ Loading...' : '🔄 Refresh'}
                      </button>
                      <button className="btn-secondary" onClick={handleGitHubLogout}>
                        🚪 Logout
                      </button>
                    </div>
                  </div>

                  {loadingRepos ? (
                    <div style={{ textAlign: 'center', padding: '40px' }}>
                      <div style={{ fontSize: '48px', marginBottom: '20px' }}>⏳</div>
                      <p>Loading repositories...</p>
                    </div>
                  ) : githubRepos.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '40px' }}>
                      <p style={{ marginBottom: '20px', color: '#999' }}>No repositories loaded yet</p>
                      <button className="btn-primary" onClick={loadGitHubRepos}>
                        Load My Repositories
                      </button>
                    </div>
                  ) : (
                    <div className="github-repos-list">
                      {githubRepos.map((repo) => (
                        <div key={repo.full_name} className="github-repo-item">
                          <div className="repo-info">
                            <strong>{repo.name}</strong>
                            <small>{repo.description || 'No description'}</small>
                            <div className="repo-meta">
                              {repo.language && (
                                <span className="repo-lang">{repo.language}</span>
                              )}
                              <span>⭐ {repo.stars}</span>
                              <span>📦 {(repo.size / 1024).toFixed(1)} MB</span>
                              {repo.private && <span style={{color: '#f59e0b'}}>🔒 Private</span>}
                            </div>
                          </div>
                          <div className="repo-actions">
                            <button
                              className="btn-primary"
                              onClick={() => selectRepo(repo)}
                            >
                              Select →
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div className="repo-header">
                    <button className="btn-back" onClick={() => {
                      setSelectedRepo(null);
                      setRepoFiles([]);
                      setSelectedFiles(new Set());
                    }}>
                      ← Back
                    </button>
                    <h3>{selectedRepo.name}</h3>
                  </div>

                  {loadingFiles ? (
                    <div style={{ textAlign: 'center', padding: '40px' }}>
                      <div style={{ fontSize: '48px', marginBottom: '20px' }}>⏳</div>
                      <p>Loading repository files...</p>
                    </div>
                  ) : repoFiles.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '40px' }}>
                      <p style={{ color: '#999' }}>No importable files found in this repository</p>
                    </div>
                  ) : (
                    <>
                      <div className="file-selection-actions">
                        <button className="btn-secondary" onClick={selectAllFiles}>
                          Select All
                        </button>
                        <button className="btn-secondary" onClick={deselectAllFiles}>
                          Deselect All
                        </button>
                        <span className="selection-count">
                          {selectedFiles.size} / {repoFiles.length} selected
                        </span>
                      </div>

                      {importProgress && (
                        <div className="import-progress">
                          <div className="progress-bar">
                            <div
                              className="progress-fill"
                              style={{ width: `${(importProgress.current / importProgress.total) * 100}%` }}
                            />
                          </div>
                          <span>
                            Importing {importProgress.current} / {importProgress.total} files...
                          </span>
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
                              onClick={(e) => e.stopPropagation()}
                            />
                            <div className="file-path">
                              <strong>{file.path.split('/').pop()}</strong>
                              <small>{file.path}</small>
                            </div>
                            <span className="file-size">{formatFileSize(file.size)}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </>
              )}
            </div>

            {selectedRepo && repoFiles.length > 0 && (
              <div className="modal-footer">
                <button
                  className="btn-secondary"
                  onClick={() => {
                    setSelectedRepo(null);
                    setRepoFiles([]);
                    setSelectedFiles(new Set());
                  }}
                >
                  Cancel
                </button>
                <button
                  className="btn-primary"
                  onClick={importSelectedFiles}
                  disabled={selectedFiles.size === 0 || importProgress}
                >
                  {importProgress ? '⏳ Importing...' : `Import ${selectedFiles.size} file${selectedFiles.size !== 1 ? 's' : ''}`}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;