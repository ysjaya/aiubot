import { state } from './state.js';
import { dom } from './dom.js';
import { setLoading, showToast, appendMessage, processCodeBlocks, autoResizeTextarea } from './ui.js';

export function setupWebSocket() {
    const message = dom.userInput.value.trim();
    
    if (!message) {
        showToast("Please type a message first.", "error");
        return;
    }
    
    if (!state.currentProjectId) {
        showToast("Please select a project first.", "error");
        return;
    }
    
    if (!state.currentConvId) {
        showToast("Please select or create a conversation first.", "error");
        return;
    }

    if (state.ws) {
        try {
            state.ws.close();
        } catch (e) {
            console.warn('Failed to close existing WebSocket');
        }
    }

    setLoading(true);

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/ai?project_id=${state.currentProjectId}&conversation_id=${state.currentConvId}`;
    
    state.ws = new WebSocket(wsUrl);

    let lastAiMessageElement = null;
    let fullResponse = '';

    state.ws.onopen = () => {
        console.log('WebSocket connected');
        
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
            } else if (data.status === 'done') {
                setLoading(false);
                processCodeBlocks(lastAiMessageElement);
                state.ws.close();
            } else if (data.status === 'error') {
                setLoading(false, 'Error');
                lastAiMessageElement.innerHTML = `<p style="color:var(--error-color);"><strong>Error:</strong> ${data.message}</p>`;
                state.ws.close();
            }
        } catch (e) {
            fullResponse += event.data;
            lastAiMessageElement.innerHTML = marked.parse(fullResponse + '█');
        }
        
        if(isScrolledToBottom) {
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }
    };

    state.ws.onclose = () => {
        setLoading(false);
        if (lastAiMessageElement && fullResponse) {
            lastAiMessageElement.innerHTML = marked.parse(fullResponse);
            processCodeBlocks(lastAiMessageElement);
        }
    };
    
    state.ws.onerror = () => {
        setLoading(false, 'Error');
        showToast('WebSocket connection failed.', 'error');
        if (lastAiMessageElement) {
            lastAiMessageElement.innerHTML = "<p><strong>Error:</strong> Could not connect to the AI service.</p>";
        }
    };
}
