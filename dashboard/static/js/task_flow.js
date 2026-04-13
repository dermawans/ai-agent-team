/**
 * Task Flow — Renders tasks with status indicators and dependency visualization.
 */

const TASK_STATUS_ICONS = {
    'pending': '⏳',
    'queued': '⏳',
    'in_progress': '🔧',
    'completed': '✅',
    'failed': '❌',
    'blocked': '🚫',
};

function renderTaskFlow(tasks) {
    const container = document.getElementById('task-flow');
    if (!tasks || tasks.length === 0) {
        container.innerHTML = '<div class="empty-state">Tasks will appear here...</div>';
        return;
    }

    let html = '';
    tasks.forEach(task => {
        const statusIcon = TASK_STATUS_ICONS[task.status] || '⏳';
        const statusClass = task.status || 'pending';
        const agentIcon = AGENT_ICONS[task.agent_type] || '🤖';

        html += `
            <div class="task-item ${statusClass}">
                <span class="task-status-icon">${statusIcon}</span>
                <div class="task-info">
                    <div class="task-title">${escapeHtml(task.title)}</div>
                    <div class="task-meta">
                        ${task.agent_type ? `<span class="task-agent-badge">${agentIcon} ${task.agent_type}</span>` : ''}
                        ${task.depends_on && task.depends_on.length > 0 ? `<span style="margin-left: 6px;">🔗 ${task.depends_on.length} dep</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;

    // Update stats
    const completed = tasks.filter(t => t.status === 'completed').length;
    const active = tasks.filter(t => t.status === 'in_progress').length;
    const pending = tasks.filter(t => ['pending', 'queued'].includes(t.status)).length;

    document.getElementById('stat-completed').textContent = `${completed} ✅`;
    document.getElementById('stat-active').textContent = `${active} 🔧`;
    document.getElementById('stat-pending').textContent = `${pending} ⏳`;
}

function updateTaskStatus(taskId, status) {
    // Re-render would be simpler; for now, find and update the task item
    // This will be called frequently via WebSocket
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
