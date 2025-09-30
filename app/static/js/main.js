import { dom } from './dom.js';
import { actions } from './actions.js';
import { setupWebSocket } from './websocket.js';
import { autoResizeTextarea, closeSidebars } from './ui.js';

// Event Listeners
dom.newProjectBtn.addEventListener('click', actions.handleNewProject);
dom.newConvBtn.addEventListener('click', actions.handleNewConversation);
dom.chatForm.addEventListener('submit', (e) => { 
    e.preventDefault(); 
    setupWebSocket(); 
});

dom.projectList.addEventListener('click', actions.handleProjectClick);
dom.convList.addEventListener('click', actions.handleConvClick);

dom.userInput.addEventListener('input', autoResizeTextarea);
dom.userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        dom.chatForm.requestSubmit();
    }
});

dom.importRepoBtn.addEventListener('click', actions.handleGitHubImport);

dom.modalCloseBtn.addEventListener('click', () => dom.githubModal.close());

// GitHub import handlers
document.addEventListener('click', (e) => {
    if (e.target.closest('#import-selected-btn')) {
        actions.handleImportSelectedFiles();
    }
    if (e.target.closest('#back-to-repos-btn')) {
        actions.handleBackToRepos();
    }
});

// Mobile sidebars
dom.toggleLeftSidebarBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    closeSidebars();
    dom.sidebarLeft.classList.add('open');
    dom.mobileOverlay.classList.remove('hidden');
});

dom.toggleRightSidebarBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    closeSidebars();
    dom.sidebarRight.classList.add('open');
    dom.mobileOverlay.classList.remove('hidden');
});

dom.mobileOverlay.addEventListener('click', closeSidebars);

// Initialize
const init = async () => {
    console.log('🚀 Initializing AI Assistant...');
    await actions.loadProjects();
    await actions.loadConversations();
    await actions.loadAttachments();
    console.log('✅ Ready');
};

init();
