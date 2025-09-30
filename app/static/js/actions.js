import { state } from './state.js';
import { api } from './api.js';
import { showToast, renderProjects, renderConversations, renderAttachments, renderChats, closeSidebars } from './ui.js';
import { dom } from './dom.js';

export const actions = {
    loadProjects: async () => {
        try {
            state.projects = await api.get('/projects');
            renderProjects();
        } catch (err) {
            showToast('Failed to load projects', 'error');
        }
    },

    loadConversations: async () => {
        if (!state.currentProjectId) {
            state.conversations = [];
            return renderConversations();
        }
        try {
            state.conversations = await api.get(`/project/${state.currentProjectId}/conversations`);
            renderConversations();
        } catch (err) {
            showToast('Failed to load conversations', 'error');
        }
    },

    loadAttachments: async () => {
        if (!state.currentConvId) {
            state.attachments = [];
            return renderAttachments([]);
        }
        try {
            const attachments = await api.get(`/conversation/${state.currentConvId}/attachments`);
            state.attachments = attachments;
            renderAttachments(attachments);
        } catch (err) {
            renderAttachments([]);
        }
    },

    handleNewProject: async () => {
        const name = prompt("Project name:");
        if (!name?.trim()) return;
        
        try {
            await api.post(`/project?name=${encodeURIComponent(name.trim())}`);
            showToast('✅ Project created');
            await actions.loadProjects();
        } catch (err) {
            showToast('Failed to create project', 'error');
        }
    },

    handleNewConversation: async () => {
        if (!state.currentProjectId) {
            showToast('Select a project first', 'error');
            return;
        }
        
        const title = prompt("Conversation title:", "New Chat");
        if (!title?.trim()) return;
        
        try {
            const newConv = await api.post(`/conversation?project_id=${state.currentProjectId}&title=${encodeURIComponent(title.trim())}`);
            state.currentConvId = newConv.id;
            state.attachments = [];
            await actions.loadConversations();
            renderChats([]);
            renderAttachments([]);
            showToast('✅ Conversation created');
        } catch (err) {
            showToast('Failed to create conversation', 'error');
        }
    },

    handleDeleteProject: async (projectId) => {
        if (!confirm("⚠️ Delete this project?\n\nAll conversations and files will be permanently deleted!")) return;
        
        try {
            await api.delete(`/project/${projectId}`);
            if (state.currentProjectId === projectId) {
                state.currentProjectId = null;
                state.currentConvId = null;
                state.conversations = [];
                state.attachments = [];
                dom.chatMessages.classList.add('hidden');
                dom.welcomeMessage.classList.remove('hidden');
                renderAttachments([]);
            }
            await actions.loadProjects();
            renderConversations();
            showToast('🗑️ Project deleted');
        } catch(err) {
            showToast('Failed to delete project', 'error');
        }
    },

    handleDeleteConversation: async (convId) => {
        if (!confirm("⚠️ Delete this conversation and all its files?")) return;
        
        try {
            await api.delete(`/conversation/${convId}`);
            if (state.currentConvId === convId) {
                state.currentConvId = null;
                state.attachments = [];
                dom.chatMessages.classList.add('hidden');
                dom.welcomeMessage.classList.remove('hidden');
                renderAttachments([]);
            }
            await actions.loadConversations();
            showToast('🗑️ Conversation deleted');
        } catch(err) {
            showToast('Failed to delete conversation', 'error');
        }
    },

    handleProjectClick: async (e) => {
        const deleteButton = e.target.closest('.delete-btn');
        if (deleteButton) {
            e.stopPropagation();
            await actions.handleDeleteProject(parseInt(deleteButton.dataset.projectId));
            return;
        }

        const projectContainer = e.target.closest('.list-item');
        if (!projectContainer) return;
        
        const projectId = parseInt(projectContainer.dataset.projectId);
        if (!projectId || isNaN(projectId) || state.currentProjectId === projectId) return;

        state.currentProjectId = projectId;
        state.currentConvId = null;
        state.conversations = [];
        state.attachments = [];
        
        renderProjects();
        renderConversations();
        
        dom.chatMessages.innerHTML = '';
        dom.chatMessages.classList.add('hidden');
        dom.welcomeMessage.classList.remove('hidden');
        
        await actions.loadConversations();
        renderAttachments([]);
        closeSidebars();
    },

    handleConvClick: async (e) => {
        const deleteButton = e.target.closest('.delete-btn');
        if (deleteButton) {
            e.stopPropagation();
            await actions.handleDeleteConversation(parseInt(deleteButton.dataset.convId));
            return;
        }

        const convContainer = e.target.closest('.list-item');
        if (!convContainer) return;
        
        const convId = parseInt(convContainer.dataset.convId);
        if (!convId || isNaN(convId) || state.currentConvId === convId) return;

        state.currentConvId = convId;
        renderConversations();
        
        try {
            const chats = await api.get(`/conversation/${state.currentConvId}/chats`);
            renderChats(chats);
            await actions.loadAttachments();
        } catch (err) {
            showToast('Failed to load conversation', 'error');
        }
        
        closeSidebars();
    },

    handleGitHubImport: async () => {
        // Auto-create project and conversation if needed
        if (!state.currentProjectId) {
            try {
                const project = await api.post(`/project?name=${encodeURIComponent('GitHub Import ' + new Date().toLocaleDateString())}`);
                state.currentProjectId = project.id;
                await actions.loadProjects();
            } catch (err) {
                showToast('Failed to create project', 'error');
                return;
            }
        }
        
        if (!state.currentConvId) {
            try {
                const conv = await api.post(`/conversation?project_id=${state.currentProjectId}&title=${encodeURIComponent('GitHub Import ' + new Date().toLocaleTimeString())}`);
                state.currentConvId = conv.id;
                await actions.loadConversations();
            } catch (err) {
                showToast('Failed to create conversation', 'error');
                return;
            }
        }
        
        // Show modal and load repos
        dom.githubModal.showModal();
        document.getElementById('github-step-1').classList.remove('hidden');
        document.getElementById('github-step-2').classList.add('hidden');
        
        try {
            const response = await api.get('/github/repos');
            const repos = response.repos || [];
            
            if (repos.length === 0) {
                document.getElementById('repo-list-container').innerHTML = '<p>No repositories found. Please connect GitHub in the integrations panel.</p>';
                return;
            }
            
            let html = '<div class="repo-list">';
            repos.forEach(repo => {
                html += `
                    <div class="repo-item" data-repo="${repo.full_name}">
                        <div class="repo-info">
                            <div class="repo-name">${repo.name}</div>
                            <div class="repo-desc">${repo.description || 'No description'}</div>
                            <div class="repo-meta">
                                ${repo.language ? `<span class="badge">${repo.language}</span>` : ''}
                                <span><i class="fas fa-star"></i> ${repo.stars}</span>
                                ${repo.private ? '<span class="badge private">Private</span>' : ''}
                            </div>
                        </div>
                        <button class="btn-small select-repo-btn" data-repo="${repo.full_name}">
                            <i class="fas fa-arrow-right"></i> Select
                        </button>
                    </div>
                `;
            });
            html += '</div>';
            
            document.getElementById('repo-list-container').innerHTML = html;
            
            // Add click handlers for repo selection
            document.querySelectorAll('.select-repo-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const repoFullName = e.target.closest('.select-repo-btn').dataset.repo;
                    await actions.selectRepoForImport(repoFullName);
                });
            });
            
        } catch (err) {
            document.getElementById('repo-list-container').innerHTML = '<p class="error">Failed to load repositories. Make sure GitHub is connected.</p>';
            showToast('Failed to load repositories', 'error');
        }
    },
    
    selectRepoForImport: async (repoFullName) => {
        const [owner, repo] = repoFullName.split('/');
        
        document.getElementById('github-step-1').classList.add('hidden');
        document.getElementById('github-step-2').classList.remove('hidden');
        
        try {
            const response = await api.get(`/github/repo/${owner}/${repo}/files`);
            const files = response.importable || [];
            
            if (files.length === 0) {
                document.getElementById('file-selection-container').innerHTML = '<p>No importable files found in this repository.</p>';
                return;
            }
            
            let html = `
                <div class="file-import-summary">
                    <p><strong>${files.length}</strong> importable files found</p>
                    <button class="btn-small" id="select-all-files-btn">Select All</button>
                </div>
                <div class="file-selection-list">
            `;
            
            files.forEach(file => {
                html += `
                    <label class="file-checkbox-item">
                        <input type="checkbox" class="file-checkbox" value="${file.path}" checked>
                        <span class="file-path">${file.path}</span>
                        <span class="file-size">${(file.size / 1024).toFixed(1)} KB</span>
                    </label>
                `;
            });
            
            html += '</div>';
            document.getElementById('file-selection-container').innerHTML = html;
            
            // Store repo info for import
            window.currentRepoImport = { repoFullName, files };
            
            // Select all handler
            document.getElementById('select-all-files-btn')?.addEventListener('click', () => {
                const checkboxes = document.querySelectorAll('.file-checkbox');
                const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                checkboxes.forEach(cb => cb.checked = !allChecked);
            });
            
        } catch (err) {
            document.getElementById('file-selection-container').innerHTML = '<p class="error">Failed to load files from repository.</p>';
            showToast('Failed to load files', 'error');
        }
    },

    handleDeleteAttachment: async (fileId) => {
        if (!confirm('🗑️ Delete this file and all its versions?')) return;
        
        try {
            await api.delete(`/attachment/${fileId}`);
            showToast('🗑️ File deleted');
            await actions.loadAttachments();
        } catch (err) {
            showToast('Failed to delete file', 'error');
        }
    },

    handleDownloadAttachment: async (fileId, filename) => {
        try {
            const response = await fetch(`/api/attachment/${fileId}/download`);
            if (!response.ok) throw new Error('Download failed');
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            showToast(`💾 Downloaded: ${filename}`);
        } catch (err) {
            showToast('Download failed', 'error');
        }
    },

    handleViewVersions: async (fileId) => {
        try {
            const versions = await api.get(`/attachment/${fileId}/versions`);
            
            dom.modalTitle.textContent = "File Version History";
            
            let html = '<div class="versions-list">';
            versions.forEach(v => {
                const statusBadge = v.status === 'latest' ? '✨ Latest' : 
                                  v.status === 'modified' ? '✏️ Modified' : 
                                  '📄 Original';
                const timestamp = new Date(v.updated_at).toLocaleString();
                
                html += `
                    <div class="version-item">
                        <div class="version-header">
                            <span class="version-badge ${v.status}">${statusBadge}</span>
                            <span class="version-num">v${v.version}</span>
                            <span class="version-time">${timestamp}</span>
                        </div>
                        ${v.modification_summary ? `<div class="version-summary">📝 ${v.modification_summary}</div>` : ''}
                        <div class="version-actions">
                            <button class="btn-small" onclick="actions.handleDownloadAttachment(${v.id}, 'v${v.version}_${v.filename}')">
                                <i class="fas fa-download"></i> Download
                            </button>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            
            dom.modalContent.innerHTML = html;
            dom.githubModal.showModal();
        } catch (err) {
            showToast('Failed to load versions', 'error');
        }
    },
    
    handleImportSelectedFiles: async () => {
        if (!window.currentRepoImport) {
            showToast('No repository selected', 'error');
            return;
        }
        
        const checkboxes = document.querySelectorAll('.file-checkbox:checked');
        const selectedPaths = Array.from(checkboxes).map(cb => cb.value);
        
        if (selectedPaths.length === 0) {
            showToast('No files selected', 'error');
            return;
        }
        
        try {
            const response = await api.post('/github/import', {
                repo_fullname: window.currentRepoImport.repoFullName,
                file_paths: selectedPaths,
                conversation_id: state.currentConvId,
                project_id: state.currentProjectId
            });
            
            showToast(`✅ Imported ${response.imported_count} files from GitHub`);
            dom.githubModal.close();
            await actions.loadAttachments();
            
        } catch (err) {
            showToast('Failed to import files', 'error');
        }
    },
    
    handleBackToRepos: () => {
        document.getElementById('github-step-1').classList.remove('hidden');
        document.getElementById('github-step-2').classList.add('hidden');
    }
};

window.actions = actions;
