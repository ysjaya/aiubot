import { state } from './state.js';

export const api = {
    get: async (url, auth = false) => {
        const headers = {};
        if (auth && state.githubToken) {
            headers['Authorization'] = `Bearer ${state.githubToken}`;
        }
        
        try {
            const response = await fetch(`/api${url}`, { 
                method: 'GET',
                headers,
                cache: 'no-cache'
            });
            
            if (!response.ok) {
                let errorMessage = `API Error: ${response.statusText}`;
                try {
                    const error = await response.json();
                    errorMessage = error.detail || errorMessage;
                } catch (e) {
                    // If can't parse JSON, use default message
                }
                throw new Error(errorMessage);
            }
            
            return response.json();
        } catch (error) {
            console.error('API GET Error:', error);
            throw error;
        }
    },

    post: async (url, data = {}, auth = false) => {
        const headers = { 
            'Content-Type': 'application/json' 
        };
        
        if (auth && state.githubToken) {
            headers['Authorization'] = `Bearer ${state.githubToken}`;
        }
        
        try {
            const response = await fetch(`/api${url}`, {
                method: 'POST',
                headers,
                body: JSON.stringify(data),
                cache: 'no-cache'
            });
            
            if (!response.ok) {
                let errorMessage = `API Error: ${response.statusText}`;
                try {
                    const error = await response.json();
                    errorMessage = error.detail || errorMessage;
                } catch (e) {
                    // If can't parse JSON, use default message
                }
                throw new Error(errorMessage);
            }
            
            return response.json();
        } catch (error) {
            console.error('API POST Error:', error);
            throw error;
        }
    },

    delete: async (url, auth = false) => {
        const headers = {};
        if (auth && state.githubToken) {
            headers['Authorization'] = `Bearer ${state.githubToken}`;
        }
        
        try {
            const response = await fetch(`/api${url}`, { 
                method: 'DELETE',
                headers,
                cache: 'no-cache'
            });
            
            if (!response.ok) {
                let errorMessage = `API Error: ${response.statusText}`;
                try {
                    const error = await response.json();
                    errorMessage = error.detail || errorMessage;
                } catch (e) {
                    // If can't parse JSON, use default message
                }
                throw new Error(errorMessage);
            }
            
            return response.json();
        } catch (error) {
            console.error('API DELETE Error:', error);
            throw error;
        }
    }
};
