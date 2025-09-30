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

    handleFileAttach: async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        
        if (!state.currentConvId) {
            showToast('Select a conversation first', 'error');
            return;
        }
        
        if (file.size > 1_000_000) {
            showToast('File too large (max 1MB)', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            await fetch(`/api/conversation/${state.currentConvId}/attach`, {
                method: 'POST',
                body: formData
            });
            showToast(`📎 Attached: ${file.name}`);
            await actions.loadAttachments();
        } catch (err) {
            showToast('Failed to attach file', 'error');
        }
        
        event.target.value = '';
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
    }
};

window.actions = actions;
