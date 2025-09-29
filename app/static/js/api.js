import { state } from './state.js';

export const api = {
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
