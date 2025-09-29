document.addEventListener('DOMContentLoaded', () => {
    // --- STATE MANAGEMENT ---
    const state = {
        projects: [],
        conversations: [],
        currentProjectId: null,
        currentConvId: null,
        ws: null,
    };

    // --- DOM ELEMENTS ---
    const projectList = document.getElementById('project-list');
    const convList = document.getElementById('conv-list');
    const newProjectBtn = document.getElementById('new-project-btn');
    const newConvBtn = document.getElementById('new-conv-btn');
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const welcomeMessage = document.getElementById('welcome-message');

    // --- API HELPERS ---
    const api = {
        get: (url) => fetch(`/api${url}`).then(res => res.json()),
        post: (url, data) => fetch(`/api${url}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        }).then(res => res.json()),
        delete: (url) => fetch(`/api${url}`, { method: 'DELETE' }).then(res => res.json()),
    };

    // --- RENDER & UI FUNCTIONS ---
    const renderProjects = () => {
        projectList.innerHTML = '';
        if (state.projects.length === 0) {
            projectList.innerHTML = '<small>No projects yet. Create one!</small>';
        }
        state.projects.forEach(p => {
            const container = document.createElement('div');
            container.className = 'list-item-container';

            const item = document.createElement('div');
            item.className = 'list-item';
            item.textContent = p.name;
            item.dataset.projectId = p.id;
            if (p.id === state.currentProjectId) {
                item.classList.add('active');
            }

            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-btn';
            deleteBtn.textContent = '🗑️';
            deleteBtn.dataset.projectId = p.id;
            
            container.appendChild(item);
            container.appendChild(deleteBtn);
            projectList.appendChild(container);
        });
    };

    const renderConversations = () => {
        convList.innerHTML = '';
        if (!state.currentProjectId) {
            convList.innerHTML = '<small>Select a project first.</small>';
            newConvBtn.disabled = true;
            return;
        }
        newConvBtn.disabled = false;
        if (state.conversations.length === 0) {
            convList.innerHTML = '<small>No conversations yet.</small>';
        }
        state.conversations.forEach(c => {
            const container = document.createElement('div');
            container.className = 'list-item-container';

            const item = document.createElement('div');
            item.className = 'list-item';
            item.textContent = c.title;
            item.dataset.convId = c.id;
            if (c.id === state.currentConvId) {
                item.classList.add('active');
            }
            
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-btn';
            deleteBtn.textContent = '🗑️';
            deleteBtn.dataset.convId = c.id;

            container.appendChild(item);
            container.appendChild(deleteBtn);
            convList.appendChild(container);
        });
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

            const downloadBtn = document.createElement('button');
            downloadBtn.textContent = 'Download';
            downloadBtn.onclick = () => {
                const lang = [...block.classList].find(c => c.startsWith('language-'))?.replace('language-', '') || 'txt';
                const filename = prompt("Enter filename:", `snippet.${lang}`);
                if (filename) {
                    const blob = new Blob([block.textContent], { type: 'text/plain' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                }
            };
            
            toolbar.appendChild(copyBtn);
            toolbar.appendChild(downloadBtn);
            wrapper.appendChild(toolbar);
        });
    };

    const appendMessage = (role, content) => {
        const div = document.createElement('div');
        div.className = `message ${role}`;
        div.innerHTML = marked.parse(content);
        chatMessages.appendChild(div);
        processCodeBlocks(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return div;
    };
    
    const renderChats = (chats) => {
        welcomeMessage.classList.add('hidden');
        chatMessages.classList.remove('hidden');
        chatMessages.innerHTML = '';
        chats.forEach(chat => {
            appendMessage('user', chat.message);
            appendMessage('ai', chat.ai_response);
        });
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };

    // --- DATA FETCHING & ACTIONS ---
    const loadProjects = async () => { /* ... sama seperti sebelumnya ... */ };
    const loadConversations = async () => { /* ... sama seperti sebelumnya ... */ };
    const handleNewProject = async () => { /* ... sama seperti sebelumnya ... */ };
    const handleNewConversation = async () => { /* ... sama seperti sebelumnya ... */ };
    const handleDeleteProject = async (projectId) => { /* ... sama seperti sebelumnya ... */ };
    const handleDeleteConversation = async (convId) => { /* ... sama seperti sebelumnya ... */ };

    // --- WEBSOCKET LOGIC ---
    const setupWebSocket = () => {
        if (state.ws) state.ws.close();
        if (!state.currentProjectId || !state.currentConvId) return;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/ai?project_id=${state.currentProjectId}&conversation_id=${state.currentConvId}`;
        state.ws = new WebSocket(wsUrl);

        let lastAiMessageElement = null;
        let fullResponse = '';

        state.ws.onopen = () => {
            const message = userInput.value.trim();
            appendMessage('user', message);
            state.ws.send(JSON.stringify({ msg: message }));
            userInput.value = '';

            lastAiMessageElement = document.createElement('div');
            lastAiMessageElement.className = 'message ai';
            const thinkingP = document.createElement('p');
            thinkingP.textContent = 'Thinking...';
            lastAiMessageElement.appendChild(thinkingP);
            chatMessages.appendChild(lastAiMessageElement);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        };

        state.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.status === 'update') {
                    const thinkingP = lastAiMessageElement.querySelector('p');
                    if (thinkingP) thinkingP.textContent = data.message;
                } else if (data.status === 'done') {
                    processCodeBlocks(lastAiMessageElement);
                    state.ws.close();
                }
            } catch (e) {
                const thinkingP = lastAiMessageElement.querySelector('p');
                if (thinkingP) thinkingP.remove();
                
                fullResponse += event.data;
                lastAiMessageElement.innerHTML = marked.parse(fullResponse + '█');
            }
            chatMessages.scrollTop = chatMessages.scrollHeight;
        };

        state.ws.onclose = () => {
            if (lastAiMessageElement) {
                lastAiMessageElement.innerHTML = marked.parse(fullResponse);
                processCodeBlocks(lastAiMessageElement);
            }
        };
        state.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            if (lastAiMessageElement) {
                lastAiMessageElement.innerHTML = "<p><strong>Error:</strong> Could not connect to the AI service.</p>";
            }
        };
    };

    // --- EVENT LISTENERS ---
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        if (userInput.value.trim() && state.currentConvId) {
            setupWebSocket();
        }
    });
    
    projectList.addEventListener('click', async (e) => {
        const target = e.target;
        if (target.classList.contains('delete-btn')) {
            handleDeleteProject(parseInt(target.dataset.projectId));
        } else if (target.closest('.list-item')) {
            const listItem = target.closest('.list-item');
            state.currentProjectId = parseInt(listItem.dataset.projectId);
            state.currentConvId = null; 
            chatMessages.innerHTML = '';
            chatMessages.classList.add('hidden');
            welcomeMessage.classList.remove('hidden');
            await loadProjects(); // Memuat ulang untuk update kelas 'active'
            await loadConversations();
        }
    });

    convList.addEventListener('click', async (e) => {
        const target = e.target;
        if (target.classList.contains('delete-btn')) {
            handleDeleteConversation(parseInt(target.dataset.convId));
        } else if (target.closest('.list-item')) {
            const listItem = target.closest('.list-item');
            state.currentConvId = parseInt(listItem.dataset.convId);
            await loadConversations(); // Memuat ulang untuk update kelas 'active'
            const chats = await api.get(`/conversation/${state.currentConvId}/chats`);
            renderChats(chats);
        }
    });
    
    // --- INITIALIZATION ---
    const init = () => {
        loadProjects();
        renderConversations();
    };

    init();
});
