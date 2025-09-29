import { dom } from './dom.js';
import { actions } from './actions.js';
import { setupWebSocket } from './websocket.js';
import { autoResizeTextarea, showToast, closeSidebars } from './ui.js';
import { checkAuth } from './auth.js';

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
dom.uploadFileBtn.addEventListener('click', () => dom.fileUploadInput.click());
dom.fileUploadInput.addEventListener('change', actions.handleFileUpload);

// Modal Listeners
dom.modalCloseBtn.addEventListener('click', () => dom.githubModal.close());
dom.modalContent.addEventListener('click', (e) => {
    if (e.target.classList.contains('github-repo-list-item')) {
        actions.handleRepoSelect(e.target.dataset.repoFullname);
    } else if (e.target.classList.contains('github-file-list-item')) {
        actions.handleFileImport(e.target.dataset.filePath);
    }
});

// Mobile Sidebar Listeners
dom.toggleLeftSidebarBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    closeSidebars();
    dom.sidebarLeft.classList.add('open');
    dom.mobileOverlay.classList.remove('hidden');
});
dom.toggleRightSidebarBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    closeSidebars();
    dom.sidebarRight.classList.add('open');
    dom.mobileOverlay.classList.remove('hidden');
});
dom.mobileOverlay.addEventListener('click', closeSidebars);

// --- INITIALIZATION ---
const init = async () => {
    checkAuth();
    await actions.loadProjects();
    await actions.loadConversations();
    await actions.loadFiles();
};

init();
