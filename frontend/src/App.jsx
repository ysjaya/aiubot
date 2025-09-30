const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    files.forEach(file => uploadFile(file));
    e.target.value = '';
  };

  // ==================== GITHUB IMPORT ====================

  const loadGitHubRepos = async () => {
    if (!githubToken) {
      alert('Please login with GitHub first');
      return;
    }

    try {
      const res = await fetch(`${API_URL}/github/repos`, {
        headers: { 'Authorization': `Bearer ${githubToken}` }
      });
      
      if (!res.ok) throw new Error('Failed to load repos');
      
      const data = await res.json();
      setGithubRepos(data.repos);
      setShowGitHubImport(true);
    } catch (err) {
      console.error('Failed to load GitHub repos:', err);
      alert('Failed to load GitHub repos. Please check your token.');
    }
  };

  const loadRepoFiles = async (repo) => {
    if (!githubToken) return;

    try {
      setSelectedRepo(repo);
      setRepoFiles([]);
      setSelectedFiles(new Set());

      const [owner, name] = repo.full_name.split('/');
      const res = await fetch(`${API_URL}/github/repo/${owner}/${name}/files`, {
        headers: { 'Authorization': `Bearer ${githubToken}` }
      });

      if (!res.ok) throw new Error('Failed to load files');

      const data = await res.json();
      setRepoFiles(data.importable);
    } catch (err) {
      console.error('Failed to load repo files:', err);
      alert('Failed to load repository files');
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
      alert('Please select at least one file');
      return;
    }

    if (!selectedConv || !selectedProject) {
      alert('Please select a conversation first');
      return;
    }

    try {
      setImportProgress({ current: 0, total: selectedFiles.size });

      const res = await fetch(`${API_URL}/github/import`, {
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

      if (!res.ok) throw new Error('Import failed');

      const data = await res.json();
      
      alert(`✅ Successfully imported ${data.imported_count} files!`);
      
      // Reload attachments
      await loadAttachments(selectedConv.id);
      
      // Close modal
      setShowGitHubImport(false);
      setSelectedRepo(null);
      setRepoFiles([]);
      setSelectedFiles(new Set());
      setImportProgress(null);

    } catch (err) {
      console.error('Import failed:', err);
      alert('Failed to import files. Please try again.');
      setImportProgress(null);
    }
  };

  const quickImportAll = async (repo) => {
    if (!selectedConv || !selectedProject) {
      alert('Please select a conversation first');
      return;
    }

    if (!confirm(`Import all valid files from ${repo.name}?`)) return;

    try {
      const [owner, name] = repo.full_name.split('/');
      const res = await fetch(
        `${API_URL}/github/import-all/${owner}/${name}?conversation_id=${selectedConv.id}&project_id=${selectedProject.id}`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${githubToken}` }
        }
      );

      if (!res.ok) throw new Error('Import failed');

      const data = await res.json();
      alert(`✅ ${data.message}`);
      
      await loadAttachments(selectedConv.id);
      setShowGitHubImport(false);

    } catch (err) {
      console.error('Quick import failed:', err);
      alert('Failed to import repository');
    }
  };import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './App.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
  const [showFileUpload, setShowFileUpload] = useState(false);
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
      const res = await fetch(`${API_URL}/projects`);
      const data = await res.json();
      setProjects(data);
    } catch (err) {
      console.error('Failed to load projects:', err);
    }
  };

  const createProject = async () => {
    if (!newProjectName.trim()) return;
    try {
      const res = await fetch(`${API_URL}/project?name=${encodeURIComponent(newProjectName)}`, {
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
      await fetch(`${API_URL}/project/${projectId}`, { method: 'DELETE' });
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
      const res = await fetch(`${API_URL}/project/${projectId}/conversations`);
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
        `${API_URL}/conversation?project_id=${selectedProject.id}&title=${encodeURIComponent(newConvTitle)}`,
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
      await fetch(`${API_URL}/conversation/${convId}?project_id=${selectedProject.id}`, {
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
      const res = await fetch(`${API_URL}/conversation/${convId}/chats?project_id=${selectedProject.id}`);
      const data = await res.json();
      setChats(data);
    } catch (err) {
      console.error('Failed to load chats:', err);
    }
  };

  const loadAttachments = async (convId) => {
    try {
      const res = await fetch(`${API_URL}/conversation/${convId}/attachments?project_id=${selectedProject.id}`);
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
        `${API_URL}/conversation/${selectedConv.id}/attach?project_id=${selectedProject.id}`,
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
      await fetch(`${API_URL}/attachment/${fileId}?project_id=${selectedProject.id}`, {
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
      const res = await fetch(`${API_URL}/attachment/${fileId}/download?project_id=${selectedProject.id}`);
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

    // Add user message immediately to UI
    const tempChat = {
      id: Date.now(),
      user: 'user',
      message: userMessage,
      ai_response: '...',
      created_at: new Date().toISOString()
    };
    setChats([...chats, tempChat]);

    try {
      const res = await fetch(`${API_URL}/chat/${selectedConv.id}?project_id=${selectedProject.id}`, {
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
                // Show status update
                setStreamingResponse(`_${parsed.message}_\n\n`);
              } else if (parsed.status === 'done') {
                // Done
                break;
              } else if (parsed.status === 'error') {
                alert(`Error: ${parsed.message}`);
              }
            } catch {
              // Regular content
              fullResponse += data;
              setStreamingResponse(fullResponse);
            }
          }
        }
      }

      // Reload chats and attachments to get updated versions
      await loadChats(selectedConv.id);
      await loadAttachments(selectedConv.id);
      setStreamingResponse('');

    } catch (err) {
      console.error('Failed to send message:', err);
      alert('Failed to send message');
      setChats(chats); // Remove temp message
    } finally {
      setLoading(false);
    }
  };

  // ==================== RENDER ====================

  const renderFileStatus = (att) => {
    const statusMap = {
      'original': '📄 Original',
      'modified': '✏️ Modified',
      'latest': '✨ Latest'
    };
    return statusMap[att.status] || '📄';
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    files.forEach(file => uploadFile(file));
    e.target.value = '';
  };

  return (
    <div className="app">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h2>🚀 AI Code Assistant</h2>
          <button 
            onClick={() => setShowNewProject(!showNewProject)}
            className="btn-icon"
            title="New Project"
          >
            ➕
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
              autoFocus
            />
            <div className="form-actions">
              <button onClick={createProject} className="btn-primary">Create</button>
              <button onClick={() => setShowNewProject(false)} className="btn-secondary">Cancel</button>
            </div>
          </div>
        )}

        <div className="projects-list">
          <h3>Projects</h3>
          {projects.map(project => (
            <div
              key={project.id}
              className={`project-item ${selectedProject?.id === project.id ? 'active' : ''}`}
            >
              <div onClick={() => setSelectedProject(project)}>
                <strong>{project.name}</strong>
                <small>{new Date(project.created_at).toLocaleDateString()}</small>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteProject(project.id);
                }}
                className="btn-delete"
                title="Delete Project"
              >
                🗑️
              </button>
            </div>
          ))}
        </div>

        {selectedProject && (
          <>
            <div className="sidebar-section">
              <div className="section-header">
                <h3>Conversations</h3>
                <button 
                  onClick={() => setShowNewConv(!showNewConv)}
                  className="btn-icon"
                  title="New Conversation"
                >
                  ➕
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
                    autoFocus
                  />
                  <div className="form-actions">
                    <button onClick={createConversation} className="btn-primary">Create</button>
                    <button onClick={() => setShowNewConv(false)} className="btn-secondary">Cancel</button>
                  </div>
                </div>
              )}

              <div className="conversations-list">
                {conversations.map(conv => (
                  <div
                    key={conv.id}
                    className={`conversation-item ${selectedConv?.id === conv.id ? 'active' : ''}`}
                  >
                    <div onClick={() => setSelectedConv(conv)}>
                      <strong>{conv.title}</strong>
                      <small>{new Date(conv.created_at).toLocaleDateString()}</small>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteConversation(conv.id);
                      }}
                      className="btn-delete"
                      title="Delete Conversation"
                    >
                      🗑️
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Main Chat Area */}
      <div className="main-content">
        {!selectedConv ? (
          <div className="empty-state">
            <h2>👋 Welcome to AI Code Assistant</h2>
            <p>Create or select a project and conversation to start coding with AI!</p>
            <div className="features">
              <div className="feature">
                <span>📂</span>
                <h3>Project Management</h3>
                <p>Isolated databases per project</p>
              </div>
              <div className="feature">
                <span>📄</span>
                <h3>File Versioning</h3>
                <p>Track all file changes like Claude</p>
              </div>
              <div className="feature">
                <span>🤖</span>
                <h3>Smart AI</h3>
                <p>Analyzes and updates code intelligently</p>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="chat-header">
              <div>
                <h2>{selectedConv.title}</h2>
                <small>{selectedProject.name}</small>
              </div>
              <div className="header-actions">
                <button
                  onClick={() => setShowFileManager(!showFileManager)}
        
