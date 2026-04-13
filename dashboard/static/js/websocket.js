/**
 * WebSocket Client — Handles real-time connection to the dashboard server.
 */

class WSClient {
    constructor() {
        this.ws = null;
        this.handlers = {};
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.connect();
    }

    connect() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/ws`;

        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            console.log('[WS] Connected');
            this.reconnectDelay = 1000;
            this.emit('connected');
            // Request initial data
            this.send({ type: 'get_projects' });
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.emit(data.type, data.data);
            } catch (e) {
                console.error('[WS] Parse error:', e);
            }
        };

        this.ws.onclose = () => {
            console.log('[WS] Disconnected. Reconnecting...');
            this.emit('disconnected');
            setTimeout(() => this.connect(), this.reconnectDelay);
            this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
        };

        this.ws.onerror = (err) => {
            console.error('[WS] Error:', err);
        };
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    on(event, handler) {
        if (!this.handlers[event]) this.handlers[event] = [];
        this.handlers[event].push(handler);
    }

    emit(event, data) {
        const handlers = this.handlers[event] || [];
        handlers.forEach(h => h(data));
    }
}

// Global WebSocket client
const ws = new WSClient();
