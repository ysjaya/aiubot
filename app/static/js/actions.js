import { state } from './state.js';
import { api } from './api.js';
import { showToast, renderProjects, renderConversations, renderFiles, renderChats, closeSidebars } from './ui.js';
import { dom } from './dom.js';

export const actions = {
    loadProjects: async () => {
        try {
            state.projects = await api.get('/projects');
            renderProjects();
        } catch (err) { console.error(err); showToast('Failed to load projects.', 'error'); }
    },
    loadConversations: async () => {
        if (!state.currentProjectId) return renderConversations();
        try {
            state.conversations = await api.get(`/project/${state.currentProjectId}/conversations`);
            renderConversations();
        } catch (err) { console.error(err); showToast('Failed to load conversations.', 'error'); }
    },
    loadFiles: async () => {
        if (!state.currentProjectId) return renderFiles([]);
        try {
            const files = await api.get(`/project/${state.currentProjectId}/files`);
            renderFiles(files);
        } catch (err) { console.error(err); renderFiles([]); }
    },
    handleNewProject: async () => {
        const name = prompt("Enter new project name:");
        if (name) {
            try {
                await api.post(`/project?name=${encodeURIComponent(name)}`);
                showToast('Project created!', 'success');
                await actions.loadProjects();
            } catch (err) { console.error(err); showToast('Failed to create project.', 'error'); }
        }
    },
    handleNewConversation: async () => {
        if (!state.currentProjectId) return;
        const title = prompt("Enter new conversation title:", "New Chat");
        if (title) {
            try {
                const newConv = await api.post(`/conversation?project_id=${state.currentProjectId}&title=${encodeURIComponent(title)}`);
                state.currentConvId = newConv.id;
                await actions.loadConversations();
                renderChats([]);
            } catch (err) { console.error(err); showToast('Failed to create conversation.', 'error'); }
        }
    },
    handleDeleteProject: async (projectId) => {
        if (confirm("Are you sure you want to delete this project?")) {
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
                showToast('Project deleted.', 'success');
            } catch(err) { console.error(err); showToast('Failed to delete project.', 'error'); }
        }
    },
    handleDeleteConversation: async (convId) => {
        if (confirm("Are you sure you want to delete this conversation?")) {
            try {
                await api.delete(`/conversation/${convId}`);
                if (state.currentConvId === convId) {
                    state.currentConvId = null;
                    dom.chatMessages.classList.add('hidden');
                    dom.welcomeMessage.classList.remove('hidden');
                }
                await actions.loadConversations();
                showToast('Conversation deleted.', 'success');
            } catch(err) { console.error(err); showToast('Failed to delete conversation.', 'error'); }
        }
    },
    handleProjectClick: async (e) => {
        const projectContainer = e.target.closest('.list-item');
        if (!projectContainer) {
            const deleteButton = e.target.closest('.delete-btn');
            if (deleteButton) actions.handleDeleteProject(parseInt(deleteButton.dataset.projectId));
            return;
        }
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
        const convContainer = e.target.closest('.list-item');
        if (!convContainer) {
             const deleteButton = e.target.closest('.delete-btn');
            if (deleteButton) actions.handleDeleteConversation(parseInt(deleteButton.dataset.convId));
            return;
        }
        const convId = parseInt(convContainer.dataset.convId);
        if (!convId || isNaN(convId) || state.currentConvId === convId) return;

        state.currentConvId = convId;
        renderConversations();
        try {
            const chats = await api.get(`/conversation/${state.currentConvId}/chats`);
            renderChats(chats);
        } catch (err) { showToast('Failed to load chats.', 'error'); console.error(err); }
        closeSidebars();
    },
    handleFileUpload: async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        if (!state.currentProjectId) return showToast('Please select a project first.', 'error');
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            await fetch(`/api/file/upload/${state.currentProjectId}`, { method: 'POST', body: formData });
            showToast('File uploaded successfully!', 'success');
            await actions.loadFiles();
        } catch (err) { showToast('File upload failed.', 'error'); }
        dom.fileUploadInput.value = '';
    },
    handleGitHubImportClick: async () => {
        if (!state.currentProjectId) return showToast('Please select a project first.', 'error');
        dom.githubModal.showModal();
        dom.modalTitle.textContent = "Your Repositories";
        dom.modalContent.innerHTML = '<em>Loading repositories...</em>';
        try {
            const repos = await api.get('/github/repos', true);
            const repoList = repos.map(repo => `<li class="github-repo-list-item" data-repo-fullname="${repo.full_name}">${repo.full_name}</li>`).join('');
            dom.modalContent.innerHTML = `<ul class="github-repo-list">${repoList}</ul>`;
        } catch (err) {
            dom.modalContent.innerHTML = '<p>Could not load repositories. Your token might be invalid or expired. Try logging in again.</p>';
        }
    },
    handleRepoSelect: async (repoFullname) => {
        state.selectedRepo = repoFullname;
        dom.modalTitle.textContent = `Files in ${repoFullname}`;
        dom.modalContent.innerHTML = '<em>Loading files...</em>';
        const files = await api.get(`/github/repo-files?repo_fullname=${repoFullname}`, true);
        const fileList = files.map(file => `<li class="github-file-list-item" data-file-path="${file}">${file}</li>`).join('');
        dom.modalContent.innerHTML = `<ul class="github-file-list">${fileList}</ul>`;
    },
    handleFileImport: async (filePath) => {
        if (!state.currentProjectId || !state.selectedRepo) return;
        try {
            await api.post(`/github/import-file?project_id=${state.currentProjectId}&repo_fullname=${state.selectedRepo}&file_path=${encodeURIComponent(filePath)}`, {}, true);
            showToast(`Imported ${filePath}!`, 'success');
            await actions.loadFiles();
            dom.githubModal.close();
        } catch(err) { showToast('Failed to import file.', 'error'); }
    }
};
