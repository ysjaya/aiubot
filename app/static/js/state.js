export const state = {
    projects: [],
    conversations: [],
    files: [],
    currentProjectId: null,
    currentConvId: null,
    isLoading: false,
    ws: null,
    githubToken: null,
    githubRepos: [],
    selectedRepos: new Set(),
};
