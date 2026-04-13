/**
 * Agent Tree — Renders the agent hierarchy with real-time status updates.
 */

const AGENT_ICONS = {
    'lead': '🏠',
    'product_manager': '📋',
    'tech_lead': '🏗️',
    'db_engineer': '🗄️',
    'backend_dev': '⚙️',
    'frontend_dev': '🎨',
    'tester': '🧪',
    'devops': '🚀',
};

const STATUS_LABELS = {
    'active': 'Active',
    'idle': 'Idle',
    'waiting': 'Waiting',
    'completed': 'Done',
    'error': 'Error',
};

function renderAgentTree(agents) {
    const container = document.getElementById('agent-tree');
    if (!agents || agents.length === 0) {
        container.innerHTML = '<div class="empty-state">Agents will appear here...</div>';
        return;
    }

    let html = '';

    // Lead Agent (always present)
    html += `
        <div class="agent-node lead" onclick="showAgentDetail('lead')">
            <span class="agent-icon">🏠</span>
            <div class="agent-info">
                <div class="agent-name">Lead Agent</div>
                <div class="agent-type">Orchestrator</div>
            </div>
            <div class="agent-status active"></div>
        </div>
    `;

    // Group agents by phase
    const productAgents = agents.filter(a => ['product_manager', 'tech_lead'].includes(a.agent_type));
    const devAgents = agents.filter(a => ['db_engineer', 'backend_dev', 'frontend_dev', 'devops'].includes(a.agent_type));
    const testAgents = agents.filter(a => ['tester'].includes(a.agent_type));

    if (productAgents.length > 0) {
        html += '<div class="agent-connector"></div>';
        html += '<div style="margin-left: 16px; margin-bottom: 8px;">';
        html += '<div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;">Product Team</div>';
        productAgents.forEach(agent => {
            html += renderAgentNode(agent);
        });
        html += '</div>';
    }

    if (devAgents.length > 0) {
        html += '<div class="agent-connector"></div>';
        html += '<div style="margin-left: 16px; margin-bottom: 8px;">';
        html += '<div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;">Dev Team</div>';
        devAgents.forEach(agent => {
            html += renderAgentNode(agent);
        });
        html += '</div>';
    }

    if (testAgents.length > 0) {
        html += '<div class="agent-connector"></div>';
        html += '<div style="margin-left: 16px; margin-bottom: 8px;">';
        html += '<div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;">QA Team</div>';
        testAgents.forEach(agent => {
            html += renderAgentNode(agent);
        });
        html += '</div>';
    }

    container.innerHTML = html;
}

function renderAgentNode(agent) {
    const icon = AGENT_ICONS[agent.agent_type] || '🤖';
    const statusClass = agent.status || 'idle';
    const isActive = agent.status === 'active';

    return `
        <div class="agent-node ${isActive ? 'active' : ''}" onclick="showAgentDetail('${agent.id}')">
            <span class="agent-icon">${icon}</span>
            <div class="agent-info">
                <div class="agent-name">${agent.display_name}</div>
                <div class="agent-type">${agent.agent_type}</div>
            </div>
            <div class="agent-status ${statusClass}"></div>
        </div>
    `;
}

function updateAgentStatus(agentId, status) {
    // Find and update the agent node
    const nodes = document.querySelectorAll('.agent-node');
    nodes.forEach(node => {
        if (node.getAttribute('onclick')?.includes(agentId)) {
            const statusDot = node.querySelector('.agent-status');
            if (statusDot) {
                statusDot.className = `agent-status ${status}`;
            }
            if (status === 'active') {
                node.classList.add('active');
            } else {
                node.classList.remove('active');
            }
        }
    });
}
