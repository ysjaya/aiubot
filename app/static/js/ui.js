import { dom } from './dom.js';
import { state } from './state.js';

export const setLoading = (loading, message = 'Ready') => {
    state.isLoading = loading;
    dom.spinner.classList.toggle('hidden', !loading);
    dom.userInput.disabled = loading;
    dom.sendBtn.disabled = loading;
    dom.aiStatusText.textContent = message;
};

export const showToast = (message, type = 'success') => {
    dom.toast.textContent = message;
    dom.toast.className = type;
    dom.toast.classList.add('show');
    setTimeout(() => dom.toast.classList.remove('show'), 3000);
};

// CRITICAL FIX: Better auto-resize for mobile
export const autoResizeTextarea = () => {
    const textarea = dom.userInput;
    
    // Reset height to auto to get proper scrollHeight
    textarea.style.height = 'auto';
    
    // Calculate new height (min 60px, max 200px)
    const newHeight = Math.max(60, Math.min(textarea.scrollHeight, 200));
    textarea.style.height = `${newHeight}px`;
    
    // CRITICAL: Scroll textarea into view on mobile
    if (window.innerWidth <= 768 && document.activeElement === textarea) {
        setTimeout(() => {
            textarea.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    }
};

export const renderProjects = () => {
    dom.projectList.innerHTML = '';
    if (state.projects.length === 0) {
        dom.projectList.innerHTML = '<div class="empty-state">No projects yet</div>';
    } else {
        state.projects.forEach(p => {
            const div = document.createElement('div');
            div.className = `list-item ${p.id === state.currentProjectId ? 'active' : ''}`;
            div.dataset.projectId = p.id;
            
            // CRITICAL: Prevent text selection on list items
            div.style.userSelect = 'none';
            div.style.webkitUserSelect = 'none';
            
            div.innerHTML = `
                <span class="list-item-text">${p.name}</span>
                <button class="btn-icon delete-btn" data-project-id="${p.id}" title="Delete project" aria-label="Delete project">
                    <i class="fas fa-trash-alt"></i>
                </button>
            `;
            dom.projectList.appendChild(div);
        });
    }
};

export const renderConversations = () => {
    dom.convList.innerHTML = '';
    dom.newConvBtn.disabled = !state.currentProjectId;
    
    if (!state.currentProjectId) {
        dom.convList.innerHTML = '<div class="empty-state">Select a project first</div>';
    } else if (state.conversations.length === 0) {
        dom.convList.innerHTML = '<div class="empty-state">No conversations yet</div>';
    } else {
        state.conversations.forEach(c => {
            const div = document.createElement('div');
            div.className = `list-item ${c.id === state.currentConvId ? 'active' : ''}`;
            div.dataset.convId = c.id;
            
            // CRITICAL: Prevent text selection on list items
            div.style.userSelect = 'none';
            div.style.webkitUserSelect = 'none';
            
            div.innerHTML = `
                <span class="list-item-text">${c.title}</span>
                <button class="btn-icon delete-btn" data-conv-id="${c.id}" title="Delete conversation" aria-label="Delete conversation">
                    <i class="fas fa-trash-alt"></i>
                </button>
            `;
            dom.convList.appendChild(div);
        });
    }
};

export const renderAttachments = (files) => {
    dom.fileList.innerHTML = '';
    dom.importRepoBtn.disabled = !state.currentConvId;
    
    if (!state.currentConvId) {
        dom.fileList.innerHTML = '<div class="empty-state">Select a conversation</div>';
    } else if (files.length === 0) {
        dom.fileList.innerHTML = '<div class="empty-state">No files attached<br><small>Click import to add files from GitHub</small></div>';
    } else {
        files.forEach(f => {
            const div = document.createElement('div');
            div.className = 'attachment-item';
            
            // CRITICAL: Prevent text selection on file items
            div.style.userSelect = 'none';
            div.style.webkitUserSelect = 'none';
            
            const statusIcons = {
                'original': '📄',
                'modified': '✏️',
                'latest': '✨'
            };
            const statusIcon = statusIcons[f.status] || '📄';
            const sizeKB = (f.size_bytes / 1024).toFixed(1);
            
            div.innerHTML = `
                <div class="attachment-header">
                    <span class="attachment-icon">${statusIcon}</span>
                    <span class="attachment-name" title="${f.filename}">${f.filename}</span>
                    <span class="attachment-version">v${f.version}</span>
                </div>
                <div class="attachment-meta">
                    <span class="attachment-size">${sizeKB} KB</span>
                    ${f.modification_summary ? `<span class="attachment-summary">${f.modification_summary}</span>` : ''}
                </div>
                <div class="attachment-actions">
                    <button class="btn-icon-small" onclick="actions.handleDownloadAttachment(${f.id}, '${f.filename}')" title="Download" aria-label="Download file">
                        <i class="fas fa-download"></i>
                    </button>
                    <button class="btn-icon-small" onclick="actions.handleViewVersions(${f.id})" title="Version history" aria-label="View versions">
                        <i class="fas fa-history"></i>
                    </button>
                    <button class="btn-icon-small delete-btn" onclick="actions.handleDeleteAttachment(${f.id})" title="Delete file" aria-label="Delete file">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            `;
            dom.fileList.appendChild(div);
        });
    }
};

export const processCodeBlocks = (element) => {
    element.querySelectorAll('pre code').forEach(block => {
        if (block.dataset.highlighted) return;
        hljs.highlightElement(block);
        block.dataset.highlighted = 'true';
        
        // CRITICAL: Allow text selection in code blocks
        block.style.userSelect = 'text';
        block.style.webkitUserSelect = 'text';
        block.style.cursor = 'text';
        
        const pre = block.parentElement;
        if (pre.parentElement.classList.contains('code-block-wrapper')) return;

        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-wrapper';
        
        // CRITICAL: Allow text selection in wrapper
        wrapper.style.userSelect = 'text';
        wrapper.style.webkitUserSelect = 'text';
        
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);
        
        const toolbar = document.createElement('div');
        toolbar.className = 'code-toolbar';
        
        const copyBtn = document.createElement('button');
        copyBtn.textContent = 'Copy';
        copyBtn.setAttribute('aria-label', 'Copy code');
        
        // CRITICAL: Better copy functionality for mobile
        copyBtn.onclick = async () => {
            try {
                const textToCopy = block.textContent;
                
                // Modern clipboard API
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(textToCopy);
                    copyBtn.textContent = 'Copied!';
                } else {
                    // Fallback for older browsers
                    const textArea = document.createElement('textarea');
                    textArea.value = textToCopy;
                    textArea.style.position = 'fixed';
                    textArea.style.left = '-999999px';
                    textArea.style.top = '-999999px';
                    document.body.appendChild(textArea);
                    textArea.focus();
                    textArea.select();
                    
                    try {
                        document.execCommand('copy');
                        copyBtn.textContent = 'Copied!';
                    } catch (err) {
                        copyBtn.textContent = 'Failed';
                    }
                    
                    textArea.remove();
                }
                
                setTimeout(() => copyBtn.textContent = 'Copy', 2000);
            } catch (err) {
                console.error('Copy failed:', err);
                copyBtn.textContent = 'Failed';
                setTimeout(() => copyBtn.textContent = 'Copy', 2000);
            }
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
    
    // CRITICAL: Allow full text selection in messages
    div.style.userSelect = 'text';
    div.style.webkitUserSelect = 'text';
    div.style.cursor = 'text';
    
    div.innerHTML = marked.parse(content);
    dom.chatMessages.appendChild(div);
    
    // CRITICAL: Ensure all children allow text selection
    div.querySelectorAll('*').forEach(el => {
        el.style.userSelect = 'text';
        el.style.webkitUserSelect = 'text';
        el.style.cursor = 'text';
    });
    
    processCodeBlocks(div);
    
    // CRITICAL: Scroll to bottom smoothly on mobile
    setTimeout(() => {
        dom.chatWindow.scrollTo({
            top: dom.chatWindow.scrollHeight,
            behavior: 'smooth'
        });
    }, 100);
    
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
    
    // Scroll to bottom after rendering
    setTimeout(() => {
        dom.chatWindow.scrollTop = dom.chatWindow.scrollHeight;
    }, 100);
};

export const closeSidebars = () => {
    dom.sidebarLeft.classList.remove('open');
    dom.sidebarRight.classList.remove('open');
    dom.mobileOverlay.classList.add('hidden');
    
    // CRITICAL: Re-enable body scroll
    document.body.style.overflow = '';
};

// CRITICAL: Open sidebar with body scroll lock
export const openSidebar = (sidebar) => {
    closeSidebars();
    sidebar.classList.add('open');
    dom.mobileOverlay.classList.remove('hidden');
    
    // CRITICAL: Prevent body scroll when sidebar is open
    document.body.style.overflow = 'hidden';
};

// CRITICAL: Better keyboard handling for mobile
export const setupKeyboardHandlers = () => {
    const userInput = dom.userInput;
    
    // Handle Enter key
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            dom.chatForm.requestSubmit();
        }
    });
    
    // Auto-resize on input
    userInput.addEventListener('input', autoResizeTextarea);
    
    // CRITICAL: Ensure textarea is focused properly on mobile
    userInput.addEventListener('focus', () => {
        // Wait for keyboard to appear
        setTimeout(() => {
            userInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 300);
    });
    
    // CRITICAL: Prevent iOS zoom on focus
    if (/iPad|iPhone|iPod/.test(navigator.userAgent)) {
        userInput.style.fontSize = '16px';
    }
};

// Initialize keyboard handlers when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupKeyboardHandlers);
} else {
    setupKeyboardHandlers();
                }
