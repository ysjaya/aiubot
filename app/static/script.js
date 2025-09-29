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

    // --- RENDER FUNCTIONS ---
    const renderProjects = () => {
        projectList.innerHTML = '';
        if (state.projects.length === 0) {
            projectList.innerHTML = '<small>No projects yet. Create one!</small>';
        }
        state.projects.forEach(p => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.textContent = p.name;
            div.dataset.projectId = p.id;
            if (p.id === state.currentProjectId) {
                div.classList.add('active');
            }
            projectList.appendChild(div);
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
            const div = document.createElement('div');
            div.className = 'list-item';
            div.textContent = c.title;
            div.dataset.convId = c.id;
            if (c.id === state.currentConvId) {
                div.classList.add('active');
            }
            convList.appendChild(div);
        });
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

    const appendMessage = (role, content) => {
        const div = document.createElement('div');
        div.className = `message ${role}`;
        
        // Use a <pre> tag inside to preserve formatting
        const pre = document.createElement('pre');
        pre.textContent = content;
        div.appendChild(pre);
        
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };


    // --- DATA FETCHING & ACTIONS ---
    const loadProjects = async () => {
        state.projects = await api.get('/projects');
        renderProjects();
    };

    const loadConversations = async () => {
        if (!state.currentProjectId) return;
        state.conversations = await api.get(`/project/${state.currentProjectId}/conversations`);
        renderConversations();
    };
    
    const handleNewProject = async () => {
        const name = prompt("Enter new project name:", `Project ${Date.now()}`);
        if (name) {
            await api.post(`/project?name=${name}`);
            await loadProjects();
        }
    };

    const handleNewConversation = async () => {
        if (!state.currentProjectId) return;
        const title = prompt("Enter new conversation title:", `Chat ${Date.now()}`);
        if (title) {
            await api.post(`/conversation?project_id=${state.currentProjectId}&title=${title}`);
            await loadConversations();
        }
    };

    const handleChatSubmit = (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message || !state.currentConvId || !state.ws) return;

        appendMessage('user', message);
        state.ws.send(JSON.stringify({ msg: message }));
        userInput.value = '';
        
        // Create a placeholder for AI response
        const aiMessagePlaceholder = document.createElement('div');
        aiMessagePlaceholder.className = 'message ai';
        const pre = document.createElement('pre');
        pre.textContent = '思考中...';
        aiMessagePlaceholder.appendChild(pre);
        chatMessages.appendChild(aiMessagePlaceholder);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };

    const setupWebSocket = () => {
        if (state.ws) {
            state.ws.close();
        }
        if (!state.currentProjectId || !state.currentConvId) return;

        const wsUrl = `ws://${window.location.host}/ws/ai?project_id=${state.currentProjectId}&conversation_id=${state.currentConvId}`;
        state.ws = new WebSocket(wsUrl);

        state.ws.onmessage = (event) => {
            const aiMessages = chatMessages.querySelectorAll('.message.ai');
            const lastAiMessage = aiMessages[aiMessages.length - 1];
            
            if (lastAiMessage) {
                const pre = lastAiMessage.querySelector('pre');
                if (pre.textContent === '思考中...') {
                    pre.textContent = ''; // Clear the thinking message
                }
                pre.textContent += event.data;
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        };

        state.ws.onclose = () => console.log('WebSocket disconnected.');
        state.ws.onerror = (error) => console.error('WebSocket error:', error);
    };


    // --- EVENT LISTENERS ---
    newProjectBtn.addEventListener('click', handleNewProject);
    newConvBtn.addEventListener('click', handleNewConversation);
    chatForm.addEventListener('submit', handleChatSubmit);

    projectList.addEventListener('click', async (e) => {
        if (e.target.classList.contains('list-item')) {
            state.currentProjectId = parseInt(e.target.dataset.projectId);
            state.currentConvId = null; // Reset conversation
            chatMessages.classList.add('hidden');
            welcomeMessage.classList.remove('hidden');
            renderProjects();
            await loadConversations();
            renderConversations();
        }
    });

    convList.addEventListener('click', async (e) => {
        if (e.target.classList.contains('list-item')) {
            state.currentConvId = parseInt(e.target.dataset.convId);
            renderConversations();
            const chats = await api.get(`/conversation/${state.currentConvId}/chats`);
            renderChats(chats);
            setupWebSocket();
        }
    });

    // --- INITIALIZATION ---
    const init = () => {
        loadProjects();
        renderConversations();
    };

    init();
});
