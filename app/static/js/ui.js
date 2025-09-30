import { dom } from './dom.js';
import { state } from './state.js';

export const setLoading = (loading, message = 'Ready') => {
    state.isLoading = loading;
    dom.spinner.classList.toggle('hidden', !loading);
    dom.userInput.disabled = loading;
    dom.sendBtn.disabled = loading;
    dom.aiStatusText.textContent = loading ? "AI is thinking..." : message;
};

export const showToast = (message, type = 'success') => {
    dom.toast.textContent = message;
    dom.toast.className = '';
    dom.toast.classList.add(type, 'show');
    setTimeout(() => dom.toast.classList.remove('show'), 3000);
};

export const autoResizeTextarea = () => {
    dom.userInput.style.height = 'auto';
    dom.userInput.style.height = `${dom.userInput.scrollHeight}px`;
};

export const renderProjects = () => {
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

export const renderConversations = () => {
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

export const renderFiles = (files) => {
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

export const processCodeBlocks = (element) => {
    element.querySelectorAll('pre code').forEach(block => {
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

export const appendMessage = (role, content) => {
    dom.welcomeMessage.classList.add('hidden');
    dom.chatMessages.classList.remove('hidden');
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerHTML = marked.parse(content);
    dom.chatMessages.appendChild(div);
    processCodeBlocks(div);
    return div;
};

export const renderChats = (chats) => {
    dom.welcomeMessage.classList.add('hidden');
    dom.chatMessages.classList.remove('hidden');
    dom.chatMessages.innerHTML = '';
    chats.forEach(chat => {
        appendMessage('user', chat.message);
        appendMessage('ai', chat.ai_response);
    });
    dom.chatWindow.scrollTop = dom.chatWindow.scrollHeight;
};

export const closeSidebars = () => {
    dom.sidebarLeft.classList.remove('open');
    dom.sidebarRight.classList.remove('open');
    dom.mobileOverlay.classList.add('hidden');
};
