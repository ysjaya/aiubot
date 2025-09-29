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
        chatMessages: document.getElementById('chat-messages'),
        welcomeMessage: document.getElementById('welcome-message'),
        aiStatusText: document.getElementById('ai-status-text'),
        spinner: document.getElementById('spinner'),
        toast: document.getElementById('toast'),
        importGithubBtn: document.getElementById('import-github-btn'),
        uploadFileBtn: document.getElementById('upload-file-btn'),
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
        dom.toast.className = type;
        dom.toast.classList.add('show');
        setTimeout(() => dom.toast.classList.remove('show'), 3000);
    };

    const autoResizeTextarea = () => {
        dom.userInput.style.height = 'auto';
        const newHeight = dom.userInput.scrollHeight;
        dom.userInput.style.height = `${newHeight}px`;
    };

    // --- API HELPERS ---
    const api = {
        get: async (url) => {
            const response = await fetch(`/api${url}`);
            if (!response.ok) throw new Error(`API Error: ${response.statusText} (${response.status})`);
            return response.json();
        },
        post: async (url, data = {}) => {
            const response = await fetch(`/api${url}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            if (!response.ok) throw new Error(`API Error: ${response.statusText} (${response.status})`);
            return response.json();
        },
        delete: async (url) => {
            const response = await fetch(`/api${url}`, { method: 'DELETE' });
            if (!response.ok) throw new Error(`API Error: ${response.statusText} (${response.status})`);
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
                const item = `
                    <div class="list-item-container">
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
                const item = `
                    <div class="list-item-container">
                        <div class="list-item ${c.id === state.currentConvId ? 'active' : ''}" data-conv-id="${c.id}">${c.title}</div>
                        <button class="icon-btn delete-btn" data-conv-id="${c.id}" data-tooltip="Delete Conversation"><i class="fas fa-trash-alt"></i></button>
                    </div>`;
                dom.convList.insertAdjacentHTML('beforeend', item);
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
        dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
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
    };

    // --- DATA FETCHING & ACTIONS ---
    const actions = {
        loadProjects: async () => {
            try {
                state.projects = await api.get('/projects');
                renderProjects();
            } catch (err) {
                showToast('Failed to load projects.', 'error');
                console.error(err);
            }
        },
        loadConversations: async () => {
            if (!state.currentProjectId) return;
            try {
                state.conversations = await api.get(`/project/${state.currentProjectId}/conversations`);
                renderConversations();
            } catch (err) {
                showToast('Failed to load conversations.', 'error');
                console.error(err);
            }
        },
        handleNewProject: async () => {
            const name = prompt("Enter new project name:");
            if (name) {
                try {
                    await api.post(`/project?name=${encodeURIComponent(name)}`);
                    showToast('Project created!', 'success');
                    await actions.loadProjects();
                } catch (err) {
                    showToast('Failed to create project.', 'error');
                    console.error(err);
                }
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
                    dom.chatMessages.innerHTML = '';
                    dom.welcomeMessage.classList.remove('hidden');
                    dom.chatMessages.classList.add('hidden');
                } catch (err) {
                     showToast('Failed to create conversation.', 'error');
                     console.error(err);
                }
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
                    }
                    await actions.loadProjects();
                    renderConversations();
                    showToast('Project deleted.', 'success');
                } catch(err) {
                    showToast('Failed to delete project.', 'error');
                    console.error(err);
                }
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
                } catch(err) {
                    showToast('Failed to delete conversation.', 'error');
                    console.error(err);
                }
            }
        },
        handleProjectClick: async (e) => {
            const projectId = parseInt(e.target.dataset.projectId);
            if (!projectId) return;

            if (e.target.closest('.delete-btn')) {
                actions.handleDeleteProject(projectId);
            } else if (state.currentProjectId !== projectId) {
                state.currentProjectId = projectId;
                state.currentConvId = null;
                state.conversations = [];
                renderProjects();
                renderConversations();
                dom.chatMessages.innerHTML = '';
                dom.chatMessages.classList.add('hidden');
                dom.welcomeMessage.classList.remove('hidden');
                await actions.loadConversations();
            }
        },
        handleConvClick: async (e) => {
            const convId = parseInt(e.target.dataset.convId);
            if (!convId) return;

            if (e.target.closest('.delete-btn')) {
                actions.handleDeleteConversation(convId);
            } else if (state.currentConvId !== convId) {
                state.currentConvId = convId;
                renderConversations();
                try {
                    const chats = await api.get(`/conversation/${state.currentConvId}/chats`);
                    renderChats(chats);
                } catch (err) {
                    showToast('Failed to load chats.', 'error');
                    console.error(err);
                }
            }
        },
    };

    // --- WEBSOCKET LOGIC ---
    const setupWebSocket = () => {
        const message = dom.userInput.value.trim();
        if (!message || !state.currentProjectId || !state.currentConvId) return;

        if (state.ws) state.ws.close();
        setLoading(true);

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/ai?project_id=${state.currentProjectId}&conversation_id=${state.currentConvId}`;
        state.ws = new WebSocket(wsUrl);

        let lastAiMessageElement = null;
        let fullResponse = '';

        state.ws.onopen = () => {
            appendMessage('user', message);
            state.ws.send(JSON.stringify({ msg: message }));
            dom.userInput.value = '';
            autoResizeTextarea();
            lastAiMessageElement = appendMessage('ai', '');
        };

        state.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.status === 'update') {
                    dom.aiStatusText.textContent = data.message;
                } else if (data.status === 'done') {
                    setLoading(false);
                    processCodeBlocks(lastAiMessageElement);
                    state.ws.close();
                } else if (data.status === 'error') {
                     setLoading(false, 'Error');
                     lastAiMessageElement.innerHTML = `<p class="error-text"><strong>Error:</strong> ${data.message}</p>`;
                     state.ws.close();
                }
            } catch (e) {
                fullResponse += event.data;
                lastAiMessageElement.innerHTML = marked.parse(fullResponse + '█');
                dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
            }
        };

        state.ws.onclose = () => {
            setLoading(false);
            if (lastAiMessageElement) {
                lastAiMessageElement.innerHTML = marked.parse(fullResponse);
                processCodeBlocks(lastAiMessageElement);
            }
        };

        state.ws.onerror = (error) => {
            setLoading(false, 'Error');
            showToast('WebSocket connection failed.', 'error');
            console.error('WebSocket error:', error);
            if (lastAiMessageElement) {
                lastAiMessageElement.innerHTML = "<p><strong>Error:</strong> Could not connect to the AI service.</p>";
            }
        };
    };

    // --- EVENT LISTENERS ---
    dom.newProjectBtn.addEventListener('click', actions.handleNewProject);
    dom.newConvBtn.addEventListener('click', actions.handleNewConversation);
    dom.chatForm.addEventListener('submit', (e) => { e.preventDefault(); setupWebSocket(); });
    dom.projectList.addEventListener('click', actions.handleProjectClick);
    dom.convList.addEventListener('click', actions.handleConvClick);
    dom.userInput.addEventListener('input', autoResizeTextarea);
    dom.userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            dom.chatForm.requestSubmit();
        }
    });

    dom.importGithubBtn.addEventListener('click', () => showToast('GitHub Import coming soon!', 'info'));
    dom.uploadFileBtn.addEventListener('click', () => showToast('File Upload coming soon!', 'info'));
    
    // --- INITIALIZATION ---
    const init = async () => {
        await actions.loadProjects();
        renderConversations();
    };

    init();
});
