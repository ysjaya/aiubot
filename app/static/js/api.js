export const api = {
    get: async (url) => {
        try {
            const response = await fetch(`/api${url}`, { 
                method: 'GET',
                cache: 'no-cache'
            });
            
            if (!response.ok) {
                let errorMessage = `API Error: ${response.statusText}`;
                try {
                    const error = await response.json();
                    errorMessage = error.detail || errorMessage;
                } catch (e) {}
                throw new Error(errorMessage);
            }
            
            return response.json();
        } catch (error) {
            console.error('API GET Error:', error);
            throw error;
        }
    },

    post: async (url, data = {}) => {
        try {
            const response = await fetch(`/api${url}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
                cache: 'no-cache'
            });
            
            if (!response.ok) {
                let errorMessage = `API Error: ${response.statusText}`;
                try {
                    const error = await response.json();
                    errorMessage = error.detail || errorMessage;
                } catch (e) {}
                throw new Error(errorMessage);
            }
            
            return response.json();
        } catch (error) {
            console.error('API POST Error:', error);
            throw error;
        }
    },

    delete: async (url) => {
        try {
            const response = await fetch(`/api${url}`, { 
                method: 'DELETE',
                cache: 'no-cache'
            });
            
            if (!response.ok) {
                let errorMessage = `API Error: ${response.statusText}`;
                try {
                    const error = await response.json();
                    errorMessage = error.detail || errorMessage;
                } catch (e) {}
                throw new Error(errorMessage);
            }
            
            return response.json();
        } catch (error) {
            console.error('API DELETE Error:', error);
            throw error;
        }
    }
};
