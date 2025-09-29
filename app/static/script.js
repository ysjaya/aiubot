document.addEventListener('DOMContentLoaded', () => {
    // --- STATE MANAGEMENT ---
    const state = {
        projects: [],
        conversations: [],
        files: [],
        currentProjectId: null,
        currentConvId: null,
        isLoading: false,
        ws: null,
        githubToken: null,
        selectedRepo: null,
    };

    // --- DOM ELEMENTS ---
    const dom = {
        projectList: document.getElementById('project-list'),
        convList: document.getElementById('conv-list'),
        fileList: document.getElementById('file-list'),
        newProjectBtn: document.getElementById('new-project-btn'),
        newConvBtn: document.getElementById('new-conv-btn'),
        chatForm: document.getElementById('chat-form'),
        userInput: document.getElementById('user-input'),
        sendBtn: document.getElementById('send-btn'),
        chatWindow: document.getElementById('chat-window'),
        chatMessages: document.getElementById('chat-messages'),
        welcomeMessage: document.getElementById('welcome-message'),
        aiStatusText: document.getElementById('ai-status-text'),
        spinner: document.getElementById('spinner'),
        toast: document.getElementById('toast'),
        importGithubBtn: document.getElementById('import-github-btn'),
        uploadFileBtn: document.getElementById('upload-file-btn'),
        fileUploadInput: document.getElementById('file-upload-input'),
        sidebarLeft: document.getElementById('sidebar-left'),
        sidebarRight: document.getElementById('sidebar-right'),
        toggleLeftSidebarBtn: document.getElementById('toggle-left-sidebar-btn'),
        toggleRightSidebarBtn: document.getElementById('toggle-right-sidebar-btn'),
        mobileOverlay: document.getElementById('mobile-overlay'),
        githubModal: document.getElementById('github-modal'),
        modalTitle: document.getElementById('modal-title'),
        modalContent: document.getElementById('modal-content'),
        modalCloseBtn: document.getElementById('modal-close-btn'),
    };

    // --- UI & STATE UPDATERS ---
    const setLoading = (loading, message = 'Ready') => {
        state.isLoading = loading;
        dom.spinner.classList.toggle('hidden', !loading);
        dom.userInput.disabled = loading;
        dom.sendBtn.disabled = loading;
        if (loading) {
            dom.aiStatusText.textContent = "AI is thinking...";
        } else {
            dom.aiStatusText.textContent = message;
        }
    };
    
    const showToast = (message, type = 'success') => {
        dom.toast.textContent = message;
        dom.toast.className = '';
        dom.toast.classList.add(type, 'show');
        setTimeout(() => dom.toast.classList.remove('show'), 3000);
    };

    const autoResizeTextarea = () => {
        dom.userInput.style.height = 'auto';
        dom.userInput.style.height = `${dom.userInput.scrollHeight}px`;
    };

    // --- API HELPERS ---
    const api = {
        get: async (url, auth = false) => {
            const headers = auth ? { 'Authorization': `Bearer ${state.githubToken}` } : {};
            const response = await fetch(`/api${url}`, { headers });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `API Error: ${response.statusText}`);
            }
            return response.json();
        },
        post: async (url, data = {}, auth = false) => {
            const headers = { 'Content-Type': 'application/json' };
            if (auth) headers['Authorization'] = `Bearer ${state.githubToken}`;
            const response = await fetch(`/api${url}`, {
                method: 'POST',
                headers,
                body: JSON.stringify(data),
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `API Error: ${response.statusText}`);
            }
            return response.json();
        },
        delete: async (url) => {
            const response = await fetch(`/api${url}`, { method: 'DELETE' });
             if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `API Error: ${response.statusText}`);
            }
            return response.json();
        },
    };

    // --- RENDER FUNCTIONS ---
    const renderProjects = () => {
        dom.projectList.innerHTML = '';
        if (state.projects.length === 0) {
            dom.projectList.innerHTML = '<small>No projects yet. Create one!</small>';
        } else {
            state.projects.forEach(p => {
                const item = `<div class="list-item-container">
                        <div class="list-item ${p.id === state.currentProjectId ? 'active' : ''}" data-project-id="${p.id}">${p.name}</div>
                        <button class="icon-btn delete-btn" data-project-id="${p.id}" data-tooltip="Delete Project"><i class="fas fa-trash-alt"></i></button>
                    </div>`;
                dom.projectList.insertAdjacentHTML('beforeend', item);
            });
        }
    };

    const renderConversations = () => {
        dom.convList.innerHTML = '';
        dom.newConvBtn.disabled = !state.currentProjectId;
        if (!state.currentProjectId) {
            dom.convList.innerHTML = '<small>Select a project first.</small>';
        } else if (state.conversations.length === 0) {
            dom.convList.innerHTML = '<small>No conversations yet.</small>';
        } else {
            state.conversations.forEach(c => {
                const item = `<div class="list-item-container">
                        <div class="list-item ${c.id === state.currentConvId ? 'active' : ''}" data-conv-id="${c.id}">${c.title}</div>
                        <button class="icon-btn delete-btn" data-conv-id="${c.id}" data-tooltip="Delete Conversation"><i class="fas fa-trash-alt"></i></button>
                    </div>`;
                dom.convList.insertAdjacentHTML('beforeend', item);
            });
        }
    };

    const renderFiles = (files) => {
        dom.fileList.innerHTML = '';
        if (files.length === 0) {
            dom.fileList.innerHTML = '<small>No files in this project yet.</small>';
        } else {
            files.forEach(f => {
                const item = `<div class="list-item-container"><div class="list-item" title="${f.path}">${f.path}</div></div>`;
                dom.fileList.insertAdjacentHTML('beforeend', item);
            });
        }
    };
    
    const processCodeBlocks = (element) => {
        const codeBlocks = element.querySelectorAll('pre code');
        codeBlocks.forEach(block => {
            if (block.dataset.highlighted) return;
            hljs.highlightElement(block);
            block.dataset.highlighted = 'true';
            const pre = block.parentElement;
            if (pre.parentElement.classList.contains('code-block-wrapper')) return;

            const wrapper = document.createElement('div');
            wrapper.className = 'code-block-wrapper';
            pre.parentNode.insertBefore(wrapper, pre);
            wrapper.appendChild(pre);
            const toolbar = document.createElement('div');
            toolbar.className = 'code-toolbar';
            const copyBtn = document.createElement('button');
            copyBtn.textContent = 'Copy';
            copyBtn.onclick = () => {
                navigator.clipboard.writeText(block.textContent).then(() => {
                    copyBtn.textContent = 'Copied!';
                    setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
                });
            };
            toolbar.appendChild(copyBtn);
            wrapper.appendChild(toolbar);
        });
    };

    const appendMessage = (role, content) => {
        dom.welcomeMessage.classList.add('hidden');
        dom.chatMessages.classList.remove('hidden');
        const div = document.createElement('div');
        div.className = `message ${role}`;
        div.innerHTML = marked.parse(content);
        dom.chatMessages.appendChild(div);
        processCodeBlocks(div);
        return div;
    };
    
    const renderChats = (chats) => {
        dom.welcomeMessage.classList.add('hidden');
        dom.chatMessages.classList.remove('hidden');
        dom.chatMessages.innerHTML = '';
        chats.forEach(chat => {
            appendMessage('user', chat.message);
            appendMessage('ai', chat.ai_response);
        });
        dom.chatWindow.scrollTop = dom.chatWindow.scrollHeight;
    };
    
    // --- AUTH LOGIC ---
    const checkAuth = () => {
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        const error = urlParams.get('error');

        if (token) {
            state.githubToken = token;
            localStorage.setItem('github_token', token);
            window.history.replaceState({}, document.title, "/");
            showToast('Successfully logged in to GitHub!', 'success');
        } else if (error) {
            showToast('GitHub authentication failed.', 'error');
            window.history.replaceState({}, document.title, "/");
        } else {
            state.githubToken = localStorage.getItem('github_token');
        }
        updateLoginStatus();
    };

    const updateLoginStatus = () => {
        const icon = dom.importGithubBtn.querySelector('i');
        if (state.githubToken) {
            dom.importGithubBtn.onclick = actions.handleGitHubImportClick;
            icon.className = 'fab fa-github';
            dom.importGithubBtn.dataset.tooltip = "Import from GitHub";
        } else {
            dom.importGithubBtn.onclick = () => { window.location.href = '/api/auth/login'; };
            icon.className = 'fas fa-sign-in-alt';
            dom.importGithubBtn.dataset.tooltip = "Login with GitHub";
        }
    };
    
    // --- ACTIONS ---
    const actions = {
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
    
    // --- WebSocket Logic ---
    const setupWebSocket = () => {
        const message = dom.userInput.value.trim();
        if (!message || !state.currentProjectId || !state.currentConvId) {
            if(!message) showToast("Please type a message first.", "error");
            if(!state.currentConvId) showToast("Please select a conversation first.", "error");
            return;
        }

        if (state.ws) state.ws.close();
        setLoading(true);

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/ai?project_id=${state.currentProjectId}&conversation_id=${state.currentConvId}`;
        state.ws = new WebSocket(wsUrl);

        let lastAiMessageElement = null;
        let fullResponse = '';

        state.ws.onopen = () => {
            appendMessage('user', message);
            dom.chatWindow.scrollTop = dom.chatWindow.scrollHeight;
            const payload = JSON.stringify({ msg: message });
            state.ws.send(payload);
            dom.userInput.value = '';
            autoResizeTextarea();
            lastAiMessageElement = appendMessage('ai', '');
        };

        state.ws.onmessage = (event) => {
            const scrollThreshold = 50;
            const chatWindow = dom.chatWindow;
            const isScrolledToBottom = chatWindow.scrollHeight - chatWindow.clientHeight <= chatWindow.scrollTop + scrollThreshold;
            
            try {
                const data = JSON.parse(event.data);
                if (data.status === 'update') {
                    dom.aiStatusText.textContent = data.message;
                } else if (data.status === '
