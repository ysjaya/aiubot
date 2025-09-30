import { state } from './state.js';
import { api } from './api.js';
import { showToast, renderProjects, renderConversations, renderFiles, renderChats, closeSidebars } from './ui.js';
import { dom } from './dom.js';
import { loginWithGitHub, isAuthenticated } from './auth.js';

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

    loadFiles: async () => {
        if (!state.currentProjectId) return renderFiles([]);
        try {
            const files = await api.get(`/project/${state.currentProjectId}/files`);
            renderFiles(files);
        } catch (err) {
            renderFiles([]);
        }
    },

    handleNewProject: async () => {
        const name = prompt("Project name:");
        if (!name?.trim()) return;
        
        try {
            await api.post(`/project?name=${encodeURIComponent(name.trim())}`);
            showToast('Project created');
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
            await actions.loadConversations();
            renderChats([]);
        } catch (err) {
            showToast('Failed to create conversation', 'error');
        }
    },

    handleDeleteProject: async (projectId) => {
        if (!confirm("Delete this project? All data will be lost!")) return;
        
        try {
            await api.delete(`/project/${projectId}`);
            if (state.currentProjectId === projectId) {
                state.currentProjectId = null;
                state.currentConvId = null;
                state.conversations = [];
                dom.chatMessages.classList.add('hidden');
                dom.welcomeMessage.classList.remove('hidden');
                await actions.loadFiles();
            }
            await actions.loadProjects();
            renderConversations();
            showToast('Project deleted');
        } catch(err) {
            showToast('Failed to delete project', 'error');
        }
    },

    handleDeleteConversation: async (convId) => {
        if (!confirm("Delete this conversation?")) return;
        
        try {
            await api.delete(`/conversation/${convId}`);
            if (state.currentConvId === convId) {
                state.currentConvId = null;
                dom.chatMessages.classList.add('hidden');
                dom.welcomeMessage.classList.remove('hidden');
            }
            await actions.loadConversations();
            showToast('Conversation deleted');
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
        
        renderProjects();
        renderConversations();
        
        dom.chatMessages.innerHTML = '';
        dom.chatMessages.classList.add('hidden');
        dom.welcomeMessage.classList.remove('hidden');
        
        await actions.loadConversations();
        await actions.loadFiles();
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
        } catch (err) {
            showToast('Failed to load chats', 'error');
        }
        
        closeSidebars();
    },

    handleFileUpload: async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        
        if (!state.currentProjectId) {
            showToast('Select a project first', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            await fetch(`/api/file/upload/${state.currentProjectId}`, { 
                method: 'POST', 
                body: formData 
            });
            showToast('File uploaded');
            await actions.loadFiles();
        } catch (err) {
            showToast('File upload failed', 'error');
        }
        
        dom.fileUploadInput.value = '';
    },

    handleGitHubImportClick: async () => {
        if (!state.currentProjectId) {
            showToast('Select a project first', 'error');
            return;
        }

        if (!isAuthenticated()) {
            if (confirm('Login with GitHub first?')) {
                loginWithGitHub();
            }
            return;
        }

        dom.githubModal.showModal();
        dom.modalTitle.textContent = "Your Repositories";
        dom.modalContent.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-secondary);">Loading...</div>';
        
        try {
            const repos = await api.get('/github/repos', true);
            state.githubRepos = repos;
            state.selectedRepos = new Set();
            
            let html = '<div>';
            repos.forEach(repo => {
                html += `
                    <div class="repo-item" data-repo="${repo.full_name}">
                        <input type="checkbox" class="checkbox repo-checkbox" data-repo="${repo.full_name}">
                        <span>${repo.full_name}</span>
                    </div>
                `;
            });
            html += '<button class="btn-import" id="import-repos-btn" disabled>Import Selected</button></div>';
            
            dom.modalContent.innerHTML = html;
            
            dom.modalContent.querySelectorAll('.repo-checkbox').forEach(cb => {
                cb.addEventListener('change', (e) => {
                    const repo = e.target.dataset.repo;
                    if (e.target.checked) {
                        state.selectedRepos.add(repo);
                    } else {
                        state.selectedRepos.delete(repo);
                    }
                    document.getElementById('import-repos-btn').disabled = state.selectedRepos.size === 0;
                });
            });
            
            document.getElementById('import-repos-btn').addEventListener('click', actions.handleImportRepos);
            
        } catch (err) {
            dom.modalContent.innerHTML = '<div style="padding:20px;color:var(--error-color);">Failed to load repositories. <button class="btn-import" onclick="window.location.href=\'/api/auth/login\'">Login Again</button></div>';
        }
    },

    handleImportRepos: async () => {
        if (state.selectedRepos.size === 0) return;
        
        const importBtn = document.getElementById('import-repos-btn');
        importBtn.disabled = true;
        importBtn.textContent = 'Importing...';
        
        try {
            const reposArray = Array.from(state.selectedRepos);
            await api.post(`/github/import-repos`, {
                project_id: state.currentProjectId,
                repos: reposArray
            }, true);
            
            showToast(`Imported ${reposArray.length} repository(ies)`);
            await actions.loadFiles();
            dom.githubModal.close();
        } catch (err) {
            showToast('Failed to import repositories', 'error');
            importBtn.disabled = false;
            importBtn.textContent = 'Import Selected';
        }
    }
};
