import { state } from './state.js';
import { showToast } from './ui.js';

export function checkAuth() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    const error = urlParams.get('error');
    
    if (error) {
        showToast('GitHub authentication failed. Please try again.', 'error');
        window.history.replaceState({}, document.title, "/");
        return;
    }
    
    if (token) {
        state.githubToken = token;
        localStorage.setItem('github_token', token);
        showToast('Successfully authenticated with GitHub!', 'success');
        window.history.replaceState({}, document.title, "/");
        return;
    }
    
    const storedToken = localStorage.getItem('github_token');
    if (storedToken) {
        state.githubToken = storedToken;
        console.log('GitHub token loaded');
    }
}

export function loginWithGitHub() {
    window.location.href = '/api/auth/login';
}

export function logout() {
    state.githubToken = null;
    localStorage.removeItem('github_token');
    showToast('Logged out successfully', 'success');
}

export function isAuthenticated() {
    return !!state.githubToken;
}
