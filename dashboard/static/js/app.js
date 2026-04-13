/**
 * Dashboard App — Main application logic, state management, and event handling.
 */

// Global state
let currentProjectId = null;
let projects = [];
let projectData = {}; // Cache of project details

// === Event Type Icons ===
const EVENT_ICONS = {
    'agent_spawned': '🤖',
    'task_started': '▶️',
    'task_completed': '✅',
    'task_failed': '❌',
    'message_sent': '💬',
    'message_received': '📨',
    'file_created': '📝',
    'file_modified': '✏️',
    'writing_file': '✏️',
    'reading_file': '🔍',
    'running_command': '⚡',
    'git_commit': '🔀',
    'error': '🔴',
    'decision': '⚖️',
    'phase_changed': '📊',
    'spec_created': '📋',
    'thinking': '💭',
    'project_created': '🚀',
};

// === WebSocket Event Handlers ===

ws.on('connected', () => {
    showToast('Connected to server', 'success');
});

ws.on('disconnected', () => {
    showToast('Disconnected. Reconnecting...', 'error');
});

ws.on('projects_list', (data) => {
    projects = data || [];
    renderProjectList();
});

ws.on('project_created', (data) => {
    projects.unshift(data);
    renderProjectList();
    selectProject(data.id);
    showToast(`Project "${data.title}" created!`, 'success');
});

ws.on('project_updated', (data) => {
    // Update in projects list
    const idx = projects.findIndex(p => p.id === data.id);
    if (idx >= 0) projects[idx] = data;
    renderProjectList();

    // Update detail view if this is the current project
    if (data.id === currentProjectId) {
        updateProjectHeader(data);
    }
});

ws.on('project_detail', (data) => {
    projectData[data.project.id] = data;
    if (data.project.id === currentProjectId) {
        renderProjectDetail(data);
    }
});

ws.on('task_created', (data) => {
    if (data.project_id === currentProjectId) {
        appendTask(data);
    }
});

ws.on('task_updated', (data) => {
    if (data.project_id === currentProjectId) {
        // Refresh the full detail
        ws.send({ type: 'get_project_detail', project_id: currentProjectId });
    }
});

ws.on('agent_status_changed', (data) => {
    if (currentProjectId) {
        updateAgentStatus(data.agent_id, data.status);
    }
});

ws.on('activity_log', (data) => {
    if (data.project_id === currentProjectId) {
        appendActivityLog(data);
    }
});

ws.on('message_sent', (data) => {
    if (data.project_id === currentProjectId) {
        appendMessage(data);
    }
});

// === Rendering Functions ===

function renderProjectList() {
    const container = document.getElementById('project-list');

    if (projects.length === 0) {
        container.innerHTML = '<div class="empty-state">No projects yet</div>';
        return;
    }

    const statusColors = {
        'pending': '#636e72',
        'planning': '#fdcb6e',
        'in_progress': '#00cec9',
        'review': '#6c5ce7',
        'completed': '#00b894',
        'failed': '#ff6b6b',
    };

    container.innerHTML = projects.map(p => `
        <div class="project-item ${p.id === currentProjectId ? 'active' : ''}"
             onclick="selectProject('${p.id}')">
            <span class="status-dot" style="background: ${statusColors[p.status] || '#636e72'}"></span>
            <span class="project-name">${escapeHtml(p.title)}</span>
        </div>
    `).join('');
}

function selectProject(projectId) {
    currentProjectId = projectId;
    renderProjectList(); // Update active state

    // Show detail view, hide welcome
    document.getElementById('welcome-screen').style.display = 'none';
    document.getElementById('project-detail').style.display = 'flex';

    // Request full project data
    ws.send({ type: 'get_project_detail', project_id: projectId });
}

function renderProjectDetail(data) {
    updateProjectHeader(data.project);
    renderAgentTree(data.agents);
    renderTaskFlow(data.tasks);
    renderActivityLogs(data.logs);
    renderMessages(data.messages);
    updateProgress(data.progress);
}

function updateProjectHeader(project) {
    document.getElementById('project-title').textContent = project.title;

    const statusEl = document.getElementById('project-status');
    statusEl.textContent = project.status.toUpperCase();
    statusEl.className = `badge badge-${project.status}`;

    document.getElementById('project-phase').textContent = `Phase: ${project.current_phase}`;

    // Show/hide retry button based on status
    const retryBtn = document.getElementById('btn-retry-project');
    retryBtn.style.display = project.status === 'failed' ? 'inline-flex' : 'none';
}

function updateProgress(progress) {
    document.getElementById('progress-fill').style.width = `${progress.percentage}%`;
    document.getElementById('progress-text').textContent = `${progress.percentage}%`;
}

function renderActivityLogs(logs) {
    const container = document.getElementById('activity-log');
    if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="empty-state">Activity will stream here...</div>';
        return;
    }

    container.innerHTML = logs.slice().reverse().map(log => renderLogEntry(log)).join('');
    container.scrollTop = container.scrollHeight;
}

function renderLogEntry(log) {
    const icon = EVENT_ICONS[log.event_type] || '📌';
    const time = formatTime(log.created_at);
    return `
        <div class="log-entry">
            <span class="log-time">${time}</span>
            <span class="log-icon">${icon}</span>
            <span class="log-text">${escapeHtml(log.description)}</span>
        </div>
    `;
}

function appendActivityLog(log) {
    const container = document.getElementById('activity-log');

    // Remove empty state if present
    const emptyState = container.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const div = document.createElement('div');
    div.innerHTML = renderLogEntry(log);
    container.appendChild(div.firstElementChild);
    container.scrollTop = container.scrollHeight;
}

function renderMessages(messages) {
    const container = document.getElementById('message-log');
    if (!messages || messages.length === 0) {
        container.innerHTML = '<div class="empty-state">Messages will appear here...</div>';
        return;
    }

    container.innerHTML = messages.slice().reverse().map(msg => renderMessageEntry(msg)).join('');
    container.scrollTop = container.scrollHeight;
}

function renderMessageEntry(msg) {
    const time = formatTime(msg.created_at);
    return `
        <div class="msg-entry ${msg.message_type}">
            <div class="msg-header">
                <span class="msg-from">${msg.from_agent_id.substring(0, 8)}</span>
                <span class="msg-type ${msg.message_type}">${msg.message_type}</span>
            </div>
            <div class="msg-content">${escapeHtml(msg.content)}</div>
            <div class="msg-time">${time} ${msg.to_agent_id ? '→ ' + msg.to_agent_id.substring(0, 8) : '→ ALL'}</div>
        </div>
    `;
}

function appendMessage(msg) {
    const container = document.getElementById('message-log');
    const emptyState = container.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const div = document.createElement('div');
    div.innerHTML = renderMessageEntry(msg);
    container.appendChild(div.firstElementChild);
    container.scrollTop = container.scrollHeight;
}

function appendTask(task) {
    // Just refresh the whole task list for simplicity
    ws.send({ type: 'get_project_detail', project_id: currentProjectId });
}

// === Agent Detail Drawer ===

function showAgentDetail(agentId) {
    const drawer = document.getElementById('agent-drawer');
    drawer.style.display = 'block';

    // Find agent data
    const data = projectData[currentProjectId];
    if (!data) return;

    const agent = data.agents.find(a => a.id === agentId);
    const agentLogs = data.logs.filter(l => l.agent_id === agentId);

    if (agentId === 'lead') {
        document.getElementById('drawer-agent-name').textContent = '🏠 Lead Agent';
        document.getElementById('drawer-agent-type').textContent = 'Orchestrator';
        document.getElementById('drawer-agent-status').textContent = 'Active';
        document.getElementById('drawer-agent-status').className = 'badge badge-active';
    } else if (agent) {
        const icon = AGENT_ICONS[agent.agent_type] || '🤖';
        document.getElementById('drawer-agent-name').textContent = `${icon} ${agent.display_name}`;
        document.getElementById('drawer-agent-type').textContent = agent.agent_type;
        document.getElementById('drawer-agent-status').textContent = agent.status;
        document.getElementById('drawer-agent-status').className = `badge badge-${agent.status}`;
    }

    // Render timeline
    const timeline = document.getElementById('drawer-timeline');
    if (agentLogs.length === 0) {
        if (agentId === 'lead') {
            const leadLogs = data.logs.filter(l => !l.agent_id);
            renderDrawerTimeline(timeline, leadLogs);
        } else {
            timeline.innerHTML = '<div class="empty-state">No activity yet</div>';
        }
    } else {
        renderDrawerTimeline(timeline, agentLogs);
    }
}

function renderDrawerTimeline(container, logs) {
    if (logs.length === 0) {
        container.innerHTML = '<div class="empty-state">No activity yet</div>';
        return;
    }

    container.innerHTML = logs.slice().reverse().map(log => {
        const icon = EVENT_ICONS[log.event_type] || '📌';
        const time = formatTime(log.created_at);
        return `
            <div class="timeline-entry">
                <span class="timeline-time">${time}</span>
                <span class="timeline-icon">${icon}</span>
                <span class="timeline-text">${escapeHtml(log.description)}</span>
            </div>
        `;
    }).join('');
}

function closeAgentDrawer() {
    document.getElementById('agent-drawer').style.display = 'none';
}

// === Modal ===

function showNewProjectModal() {
    document.getElementById('modal-new-project').style.display = 'flex';
    document.getElementById('input-title').focus();
}

function hideNewProjectModal() {
    document.getElementById('modal-new-project').style.display = 'none';
}

function createProject(event) {
    event.preventDefault();

    const title = document.getElementById('input-title').value.trim();
    const description = document.getElementById('input-description').value.trim();
    const targetPath = document.getElementById('input-target-path').value.trim();

    if (!title || !description) {
        showToast('Please fill in title and description', 'error');
        return;
    }

    ws.send({
        type: 'create_project',
        title,
        description,
        target_path: targetPath || null,
    });

    hideNewProjectModal();

    // Clear form
    document.getElementById('form-new-project').reset();
}

// === Retry Project ===

function retryProject() {
    if (!currentProjectId) return;

    ws.send({
        type: 'resume_project',
        project_id: currentProjectId,
    });

    showToast('Resuming project...', 'info');

    // Hide retry button immediately
    document.getElementById('btn-retry-project').style.display = 'none';
}

// === Toast Notifications ===

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// === Utility ===

function formatTime(isoString) {
    if (!isoString) return '--:--';
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

// === Button Event Listeners ===

document.getElementById('btn-new-project').addEventListener('click', showNewProjectModal);

// Keyboard shortcut: Escape to close drawers/modals
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        hideNewProjectModal();
        closeAgentDrawer();
    }
});
