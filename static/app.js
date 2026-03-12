// API Base URL
const API_BASE = '';

// Auth functions
function logout() {
    window.location.href = '/logout';
}

// Check if user is authenticated
function isAuthenticated() {
    // Session-based auth, backend will redirect if not authenticated
    return true;
}

// Document functions
async function uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${API_BASE}/api/documents/upload`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${authToken}`
        },
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Upload failed');
    }
    
    return response.json();
}

async function listDocuments() {
    const response = await fetch(`${API_BASE}/api/documents`, {
        headers: getHeaders()
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch documents');
    }
    
    return response.json();
}

async function deleteDocument(docId) {
    const response = await fetch(`${API_BASE}/api/documents/${docId}`, {
        method: 'DELETE',
        headers: getHeaders()
    });
    
    if (!response.ok) {
        throw new Error('Failed to delete document');
    }
    
    return response.json();
}

// Project functions
async function createProject(name, questionnaireFile) {
    const formData = new FormData();
    formData.append('name', name);
    formData.append('questionnaire', questionnaireFile);
    
    const response = await fetch(`${API_BASE}/api/projects`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${authToken}`
        },
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Project creation failed');
    }
    
    return response.json();
}

async function listProjects() {
    const response = await fetch(`${API_BASE}/api/projects`, {
        headers: getHeaders()
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch projects');
    }
    
    return response.json();
}

async function getProject(projectId) {
    const response = await fetch(`${API_BASE}/api/projects/${projectId}`, {
        headers: getHeaders()
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch project');
    }
    
    return response.json();
}

async function getProjectQuestions(projectId) {
    const response = await fetch(`${API_BASE}/api/projects/${projectId}/questions`, {
        headers: getHeaders()
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch questions');
    }
    
    return response.json();
}

async function generateAnswers(projectId) {
    const response = await fetch(`${API_BASE}/api/projects/${projectId}/generate`, {
        method: 'POST',
        headers: getHeaders()
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Answer generation failed');
    }
    
    return response.json();
}

async function updateAnswer(answerId, answerText) {
    const response = await fetch(`${API_BASE}/api/answers/${answerId}`, {
        method: 'PUT',
        headers: getHeaders(),
        body: JSON.stringify({ answer_text: answerText })
    });
    
    if (!response.ok) {
        throw new Error('Failed to update answer');
    }
    
    return response.json();
}

// Utility functions
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(alertDiv, container.firstChild);
        setTimeout(() => alertDiv.remove(), 5000);
    }
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function getConfidenceClass(confidence) {
    if (confidence >= 0.7) return 'confidence-high';
    if (confidence >= 0.4) return 'confidence-medium';
    return 'confidence-low';
}

function getConfidenceLabel(confidence) {
    if (confidence >= 0.7) return 'High';
    if (confidence >= 0.4) return 'Medium';
    return 'Low';
}
