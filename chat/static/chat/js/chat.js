// Initialize Mermaid.js for LangGraph visualization
mermaid.initialize({ startOnLoad: false, theme: 'default' });

const chatbox = document.getElementById('chatbox');
const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message');
const typingIndicator = document.getElementById('typing-indicator');
const micBtn = document.getElementById('mic-btn');
const sendStopBtn = document.getElementById('send-stop-btn');

const SEND_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
const STOP_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"></rect></svg>';

function showStopButton() {
    sendStopBtn.innerHTML = STOP_SVG + ' Stop';
    sendStopBtn.classList.add('stop-mode');
    sendStopBtn.type = 'button';
    sendStopBtn.onclick = function() {
        controlAgent('stop');
        showSendButton();
    };
}

function showSendButton() {
    sendStopBtn.innerHTML = SEND_SVG + ' Send';
    sendStopBtn.classList.remove('stop-mode');
    sendStopBtn.type = 'submit';
    sendStopBtn.onclick = null;
}

let conversationHistory = [];
let currentSessionId = null;
let saveTimer = null;

// Configure marked.js
marked.setOptions({
    breaks: true,
    gfm: true,
    highlight: function(code, lang) {
        return code; // In a real app, use Highlight.js here
    }
});

function appendMessage(sender, text, isPending = false, pendingTools = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    // Render Markdown for agent, plain text for user (security)
    if (sender === 'agent') {
        bubble.innerHTML = marked.parse(text);
    } else {
        bubble.textContent = text;
    }
    
    if (isPending && pendingTools) {
        const toolCard = document.createElement('div');
        toolCard.className = 'tool-card';
        
        toolCard.innerHTML = `
            <div class="tool-header">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>
                Action Required
            </div>
            <div class="tool-list">
                ${pendingTools.map(tool => `
                    <div class="tool-item">
                        <strong>${tool.name}</strong>(${JSON.stringify(tool.arguments)})
                    </div>
                `).join('')}
            </div>
            <div class="approval-actions">
                <button class="btn-approve" onclick="handleToolApproval('approved', ${JSON.stringify(pendingTools).replace(/"/g, '&quot;')}, this)">Approve All</button>
                <button class="btn-deny" onclick="handleToolApproval('denied', ${JSON.stringify(pendingTools).replace(/"/g, '&quot;')}, this)">Deny</button>
            </div>
        `;
        bubble.appendChild(toolCard);
    }
    
    messageDiv.appendChild(bubble);
    chatbox.appendChild(messageDiv);
    chatbox.scrollTop = chatbox.scrollHeight;
}

async function appendMermaidGraph(mermaidCode, description) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message agent';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    // Add description
    if (description) {
        const desc = document.createElement('div');
        desc.innerHTML = marked.parse(description);
        desc.style.marginBottom = '1rem';
        bubble.appendChild(desc);
    }

    // Render the Mermaid diagram
    const graphContainer = document.createElement('div');
    graphContainer.style.cssText = 'background:#f8fafc;border-radius:12px;padding:1.5rem;text-align:center;overflow-x:auto;';
    const graphId = 'mermaid-' + Date.now();
    try {
        const { svg } = await mermaid.render(graphId, mermaidCode);
        graphContainer.innerHTML = svg;
    } catch (err) {
        graphContainer.innerHTML = '<pre style="text-align:left;font-size:0.8rem;">' + escapeHtml(mermaidCode) + '</pre>';
        console.error('Mermaid render error:', err);
    }

    bubble.appendChild(graphContainer);
    messageDiv.appendChild(bubble);
    chatbox.appendChild(messageDiv);
    chatbox.scrollTop = chatbox.scrollHeight;
}

function appendExecutionPath(path) {
    const pathDiv = document.createElement('div');
    pathDiv.style.cssText = 'display:flex;align-items:center;justify-content:center;gap:0.25rem;padding:0.5rem 1rem;margin:0.25rem auto;max-width:fit-content;flex-wrap:wrap;';

    const label = document.createElement('span');
    label.textContent = 'Graph path:';
    label.style.cssText = 'font-size:0.7rem;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;margin-right:0.25rem;';
    pathDiv.appendChild(label);

    path.forEach((node, i) => {
        // Node pill
        const pill = document.createElement('span');
        pill.textContent = node;
        pill.style.cssText = 'font-size:0.72rem;font-family:monospace;padding:0.15rem 0.5rem;border-radius:9999px;font-weight:500;';
        const isError = node.endsWith(' \u2717');
        if (isError) {
            pill.style.background = '#fee2e2';
            pill.style.color = '#991b1b';
            pill.style.border = '1px solid #fca5a5';
            pill.style.fontWeight = '700';
        } else if (node === '__start__' || node === '__end__') {
            pill.style.background = '#e0e7ff';
            pill.style.color = '#4338ca';
        } else if (node === 'call_model') {
            pill.style.background = '#dbeafe';
            pill.style.color = '#1d4ed8';
        } else if (node === 'collect_dry_run') {
            pill.style.background = '#fef3c7';
            pill.style.color = '#92400e';
        } else if (node === 'execute_or_hold_tools') {
            pill.style.background = '#d1fae5';
            pill.style.color = '#065f46';
        } else if (node === 'format_output') {
            pill.style.background = '#ede9fe';
            pill.style.color = '#5b21b6';
        } else {
            pill.style.background = '#f1f5f9';
            pill.style.color = '#475569';
        }
        pathDiv.appendChild(pill);

        // Arrow between nodes
        if (i < path.length - 1) {
            const arrow = document.createElement('span');
            arrow.textContent = '\u2192';
            arrow.style.cssText = 'color:#94a3b8;font-size:0.8rem;';
            pathDiv.appendChild(arrow);
        }
    });

    chatbox.appendChild(pathDiv);
    chatbox.scrollTop = chatbox.scrollHeight;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}

function appendDryRunPlan(text, dryRunPlan) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message agent';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    const toolCard = document.createElement('div');
    toolCard.className = 'tool-card';

    // Store plan on window keyed by unique id so onclick never serialises
    // user-controlled strings into an HTML attribute
    const planId = 'dryRunPlan_' + Date.now();
    window[planId] = dryRunPlan;

    toolCard.innerHTML = `
        <div class="tool-header">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
            Plan (${dryRunPlan.length} step${dryRunPlan.length !== 1 ? 's' : ''})
        </div>
        <div class="dry-run-summary">${marked.parse(text)}</div>
        <div class="tool-list">
            ${dryRunPlan.map((step, i) => `
                <div class="tool-item">
                    <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.25rem;">
                        <span style="background:#6366f1;color:#fff;border-radius:50%;width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:0.7rem;font-weight:700;flex-shrink:0;">${i + 1}</span>
                        <strong style="font-family:sans-serif;font-size:0.85rem;">${escapeHtml(step.summary)}</strong>
                    </div>
                    <div style="color:#64748b;font-size:0.75rem;padding-left:1.75rem;">${escapeHtml(step.name)}(${escapeHtml(JSON.stringify(step.arguments))})</div>
                </div>
            `).join('')}
        </div>
        <div class="approval-actions">
            <button class="btn-approve" data-plan-id="${planId}" onclick="handleDryRunApproval('dry_run_approved', this)">✓ Approve &amp; Execute</button>
            <button class="btn-deny"    data-plan-id="${planId}" onclick="handleDryRunApproval('dry_run_denied',    this)">✕ Deny</button>
        </div>
    `;

    bubble.appendChild(toolCard);
    messageDiv.appendChild(bubble);
    chatbox.appendChild(messageDiv);
    chatbox.scrollTop = chatbox.scrollHeight;
}

async function handleDryRunApproval(status, buttonEl) {
    const planId   = buttonEl.dataset.planId;
    const plan     = window[planId];
    delete window[planId];                          // one-shot cleanup

    const card = buttonEl.closest('.tool-card');
    const label = status === 'dry_run_approved' ? 'approved' : 'denied';
    card.innerHTML = `<div style="text-align:center;color:var(--text-muted);font-size:0.8rem;padding:0.5rem;">Plan ${label}...</div>`;

    showTypingIndicator();
    showStopButton();

    try {
        const response = await fetch('/api/chat/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: status,
                dry_run_plan: plan,
                history: conversationHistory
            })
        });

        const data = await response.json();
        handleResponse(data);
    } catch (error) {
        hideTypingIndicator();
        showSendButton();
        appendMessage('agent', '❌ Error processing dry run decision.');
        console.error('Dry run approval failed', error);
    }
}

async function handleToolApproval(status, pendingTools, buttonEl) {
    const card = buttonEl.closest('.tool-card');
    card.innerHTML = `<div style="text-align: center; color: var(--text-muted); font-size: 0.8rem; padding: 0.5rem;">Tool request ${status}...</div>`;

    showTypingIndicator();
    showStopButton();

    try {
        const response = await fetch('/api/chat/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: status,
                pending_tools: pendingTools,
                history: conversationHistory
            })
        });

        const data = await response.json();
        handleResponse(data);
    } catch (error) {
        hideTypingIndicator();
        showSendButton();
        appendMessage('agent', '❌ Error processing tool approval.');
        console.error('Approval failed', error);
    }
}

function showTypingIndicator() {
    typingIndicator.style.display = 'flex';
    chatbox.scrollTop = chatbox.scrollHeight;
}

function hideTypingIndicator() {
    typingIndicator.style.display = 'none';
}

function handleResponse(data) {
    hideTypingIndicator();
    showSendButton();

    if (data.history) conversationHistory = data.history;

    if (data.status === 'pending') {
        appendMessage('agent', data.response || 'I need to perform some actions:', true, data.pending_tools);
    } else if (data.status === 'dry_run') {
        appendDryRunPlan(data.response || 'Here is the planned action(s):', data.dry_run_plan);
    } else if (data.response) {
        appendMessage('agent', data.response);
    } else if (data.error || data.message) {
        appendMessage('agent', `⚠️ ${data.error || data.message}`);
    }

    // Show the LangGraph execution path
    if (data.execution_path && data.execution_path.length > 0) {
        appendExecutionPath(data.execution_path);
    }

    // Shut down server if requested (quit/exit)
    if (data.shutdown) {
        setTimeout(async () => {
            try {
                await fetch('/api/shutdown/', { method: 'POST' });
            } catch (e) { /* server is shutting down */ }
        }, 1500);
        return;
    }

    // Auto-save chat session (debounced, fire-and-forget)
    scheduleAutoSave();
}

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = messageInput.value.trim();
    if (!message) return;

    appendMessage('user', message);
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Handle /graph command locally - renders the LangGraph visualization
    if (message.toLowerCase() === '/graph') {
        showTypingIndicator();
        try {
            const res = await fetch('/api/graph/');
            const data = await res.json();
            hideTypingIndicator();
            if (data.mermaid) {
                appendMermaidGraph(data.mermaid, data.description || '');
            } else {
                appendMessage('agent', data.error || 'Could not load graph.');
            }
        } catch (err) {
            hideTypingIndicator();
            appendMessage('agent', 'Failed to load graph.');
            console.error(err);
        }
        return;
    }

    // Handle /test-error command - simulates a failure at a graph node
    if (message.toLowerCase().startsWith('/test-error')) {
        const parts = message.trim().split(/\s+/);
        const node = parts[1] || 'call_model';
        showTypingIndicator();
        try {
            const res = await fetch('/api/test-error/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ node: node })
            });
            const data = await res.json();
            hideTypingIndicator();
            appendMessage('agent', data.message || data.error || 'Test error armed.');
            if (!data.error) {
                appendMessage('agent', 'Now send any message to trigger the simulated failure.');
            }
        } catch (err) {
            hideTypingIndicator();
            appendMessage('agent', 'Failed to set test error.');
            console.error(err);
        }
        return;
    }

    showTypingIndicator();
    showStopButton();

    try {
        const response = await fetch('/api/chat/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                history: conversationHistory
            })
        });

        const data = await response.json();
        handleResponse(data);
    } catch (error) {
        hideTypingIndicator();
        showSendButton();
        appendMessage('agent', '❌ Connection error. Please try again.');
        console.error('Request failed', error);
    }
});
async function controlAgent(action) {
    try {
        const res = await fetch('/api/agent/control/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });

        const data = await res.json();
        if (data.message) {
            appendMessage('agent', data.message);
        }

        if (action === 'stop') {
            dismissPendingApprovals();
            cleanHistoryAfterStop();
        }
    } catch (err) {
        appendMessage('agent', '⚠️ Failed to control agent.');
        console.error(err);
    }
}

function cleanHistoryAfterStop() {
    // Walk backwards — find the last assistant message with orphaned tool_calls
    for (let i = conversationHistory.length - 1; i >= 0; i--) {
        const msg = conversationHistory[i];
        if (msg.role === 'assistant' && msg.tool_calls && msg.tool_calls.length > 0) {
            // Check for matching tool responses after this index
            const toolCallIds = new Set(msg.tool_calls.map(tc => tc.id));
            const respondedIds = new Set();
            for (let j = i + 1; j < conversationHistory.length; j++) {
                if (conversationHistory[j].role === 'tool') {
                    respondedIds.add(conversationHistory[j].tool_call_id);
                }
            }
            const allResponded = [...toolCallIds].every(id => respondedIds.has(id));
            if (!allResponded) {
                conversationHistory.splice(i, 1);
                return;
            }
            break;
        }
        if (msg.role !== 'tool') {
            break;
        }
    }
}

function dismissPendingApprovals() {
    // Remove all plan approval and tool approval button groups from the DOM
    document.querySelectorAll('.btn-approve, .btn-deny').forEach(btn => {
        const card = btn.closest('.tool-card');
        if (card) {
            card.innerHTML = '<div style="text-align:center;color:var(--text-muted);font-size:0.8rem;padding:0.5rem;">Stopped by user.</div>';
        }
    });
}

// ─── Speech-to-Text (Web Speech API) ────────────────────────

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let isListening = false;
let sttExistingText = '';   // text already in the textarea when mic started
let sttFinalText    = '';   // accumulated final transcripts this session

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous    = false;
    recognition.interimResults = true;
    recognition.lang          = 'en-US';

    recognition.onresult = (event) => {
        let interimText = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
                sttFinalText += event.results[i][0].transcript;
            } else {
                interimText  += event.results[i][0].transcript;
            }
        }
        const sep = sttExistingText && (sttFinalText || interimText) ? ' ' : '';
        messageInput.value = sttExistingText + sep + sttFinalText + interimText;
        messageInput.dispatchEvent(new Event('input')); // trigger auto-resize
    };

    recognition.onend = () => {
        isListening = false;
        micBtn.classList.remove('listening');
        const sep = sttExistingText && sttFinalText ? ' ' : '';
        messageInput.value = sttExistingText + sep + sttFinalText;
        messageInput.dispatchEvent(new Event('input'));
        messageInput.focus();
    };

    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        isListening = false;
        micBtn.classList.remove('listening');
        if (event.error === 'not-allowed') {
            appendMessage('agent', '⚠️ Microphone access was denied. Please allow it in your browser settings.');
        }
    };
} else {
    // Browser does not support the Web Speech API
    micBtn.classList.add('unsupported');
    micBtn.title = 'Voice input is not supported in this browser';
}

function toggleMic() {
    if (!recognition) return;

    if (isListening) {
        recognition.stop(); // triggers onend after finalising
        return;
    }

    // Snapshot whatever the user already typed so we can append to it
    sttExistingText = messageInput.value;
    sttFinalText    = '';
    isListening     = true;
    micBtn.classList.add('listening');
    recognition.start();
}

// ─── Chat Session Management ────────────────────────────────

function generateTitle() {
    const firstUserMsg = conversationHistory.find(msg => msg.role === 'user');
    if (firstUserMsg && firstUserMsg.content) {
        return firstUserMsg.content.substring(0, 60);
    }
    return 'New Chat';
}

function scheduleAutoSave() {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => saveCurrentChat(), 800);
}

async function saveCurrentChat() {
    if (saveTimer) { clearTimeout(saveTimer); saveTimer = null; }
    if (conversationHistory.length === 0) return;
    try {
        const body = { history: conversationHistory, title: generateTitle() };
        if (currentSessionId) body.session_id = currentSessionId;
        const res = await fetch('/api/chats/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (data.session_id) {
            currentSessionId = data.session_id;
            localStorage.setItem('lastSessionId', String(currentSessionId));
        }
    } catch (err) {
        console.error('Auto-save failed', err);
    }
}

function toggleHistoryPanel() {
    const panel = document.getElementById('history-panel');
    if (panel.style.display === 'none') {
        loadHistorySessions();
        panel.style.display = 'block';
    } else {
        panel.style.display = 'none';
    }
}

async function loadHistorySessions() {
    try {
        const res = await fetch('/api/chats/');
        const data = await res.json();
        const list = document.getElementById('history-list');
        list.innerHTML = '';

        if (!data.sessions || data.sessions.length === 0) {
            list.innerHTML = '<div style="padding:1rem;color:var(--text-muted);text-align:center;font-size:0.875rem;">No saved chats yet</div>';
            return;
        }

        data.sessions.forEach(session => {
            const item = document.createElement('div');
            item.className = 'history-item' + (session.id === currentSessionId ? ' active' : '');
            item.innerHTML = `
                <div class="history-item-content" onclick="loadChat(${session.id})">
                    <div class="history-item-title">${escapeHtml(session.title)}</div>
                    <div class="history-item-date">${escapeHtml(session.updated_at)}</div>
                </div>
                <button class="btn-delete-chat" onclick="deleteChat(${session.id}, event)" title="Delete">✕</button>
            `;
            list.appendChild(item);
        });
    } catch (err) {
        console.error('Failed to load history', err);
    }
}

async function newChat() {
    if (conversationHistory.length > 0) {
        await saveCurrentChat();
    }
    conversationHistory = [];
    currentSessionId = null;
    localStorage.removeItem('lastSessionId');
    chatbox.innerHTML = '';
    document.getElementById('history-panel').style.display = 'none';
    messageInput.focus();
}

async function loadChat(sessionId) {
    try {
        // Persist whatever is currently open before switching
        if (conversationHistory.length > 0 && currentSessionId !== sessionId) {
            await saveCurrentChat();
        }

        const res = await fetch(`/api/chats/${sessionId}/`);
        if (!res.ok) {
            appendMessage('agent', '⚠️ Chat not found.');
            return;
        }
        const data = await res.json();

        conversationHistory = data.history;
        currentSessionId = data.session_id;
        localStorage.setItem('lastSessionId', String(currentSessionId));

        // Re-render visible messages (user + assistant only; tool messages
        // stay in the history array as context for the next API call)
        chatbox.innerHTML = '';
        conversationHistory.forEach(msg => {
            if (msg.role === 'user' && msg.content) {
                appendMessage('user', msg.content);
            } else if (msg.role === 'assistant' && msg.content) {
                appendMessage('agent', msg.content);
            }
        });

        document.getElementById('history-panel').style.display = 'none';
        messageInput.focus();
    } catch (err) {
        appendMessage('agent', '⚠️ Failed to load chat.');
        console.error(err);
    }
}

async function deleteChat(sessionId, event) {
    event.stopPropagation();
    try {
        await fetch(`/api/chats/${sessionId}/`, { method: 'DELETE' });
        if (currentSessionId === sessionId) {
            currentSessionId = null;
            localStorage.removeItem('lastSessionId');
        }
        await loadHistorySessions(); // refresh the list in place
    } catch (err) {
        console.error('Delete failed', err);
    }
}

async function restoreLastSession() {
    const lastId = localStorage.getItem('lastSessionId');
    if (!lastId) return;
    try {
        const res = await fetch(`/api/chats/${lastId}/`);
        if (!res.ok) { localStorage.removeItem('lastSessionId'); return; }
        const data = await res.json();

        conversationHistory = data.history;
        currentSessionId = data.session_id;

        conversationHistory.forEach(msg => {
            if (msg.role === 'user' && msg.content) {
                appendMessage('user', msg.content);
            } else if (msg.role === 'assistant' && msg.content) {
                appendMessage('agent', msg.content);
            }
        });
    } catch (err) {
        localStorage.removeItem('lastSessionId');
        console.error('Restore failed', err);
    }
}

// Initial welcome message (optional)
// appendMessage('agent', 'Hello! How can I help you today?');
restoreLastSession();
messageInput.focus();

// Handle Shift + Enter for new lines, Enter for submit
// (Also handles file autocomplete keyboard navigation)
messageInput.addEventListener('keydown', (e) => {
    if (fileAutocompleteVisible) {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            fileAutocompleteIndex = Math.min(fileAutocompleteIndex + 1, fileFilteredFiles.length - 1);
            updateAutocompleteHighlight();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            fileAutocompleteIndex = Math.max(fileAutocompleteIndex - 1, 0);
            updateAutocompleteHighlight();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            selectFileAutocompleteItem(fileAutocompleteIndex);
        } else if (e.key === 'Escape') {
            e.preventDefault();
            hideFileAutocomplete();
        } else if (e.key === 'Tab') {
            e.preventDefault();
            selectFileAutocompleteItem(fileAutocompleteIndex);
        }
        return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    }
});

// Auto-resize textarea
messageInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

// ─── File Autocomplete (@filename) ──────────────────────────
const fileAutocompleteEl = document.getElementById('file-autocomplete');
let fileAutocompleteVisible = false;
let fileAutocompleteIndex = 0;
let fileAutocompleteFiles = [];   // full list from API
let fileFilteredFiles = [];       // filtered by query
let fileAtTriggerPos = -1;        // cursor pos where @ was typed
let fileAutocompleteFetchCache = null;

// Detect @ trigger on every input change
messageInput.addEventListener('input', function fileAutocompleteInputHandler() {
    const cursorPos = this.selectionStart;
    const text = this.value.substring(0, cursorPos);

    // Find the last @ that's at start of text or preceded by whitespace
    let atPos = -1;
    for (let i = text.length - 1; i >= 0; i--) {
        if (text[i] === '@') {
            if (i === 0 || /\s/.test(text[i - 1])) {
                atPos = i;
            }
            break;
        }
        // If we encounter a space before finding @, stop
        if (text[i] === ' ' || text[i] === '\n') break;
    }

    if (atPos >= 0) {
        const query = text.substring(atPos + 1);
        // Only trigger if query has no spaces (still typing filename)
        if (!/\s/.test(query)) {
            fileAtTriggerPos = atPos;
            showFileAutocomplete(query);
            return;
        }
    }

    hideFileAutocomplete();
});

async function fetchDirectoryFiles() {
    try {
        const res = await fetch('/api/files/');
        const data = await res.json();
        if (data.files) {
            fileAutocompleteFiles = data.files;
            fileAutocompleteFetchCache = data;
        }
    } catch (err) {
        console.error('Failed to fetch directory files', err);
        fileAutocompleteFiles = [];
    }
}

async function showFileAutocomplete(query) {
    // Fetch files if not cached
    if (!fileAutocompleteFetchCache) {
        await fetchDirectoryFiles();
    }

    // Filter by query (case-insensitive, match against name or rel_path)
    const q = query.toLowerCase();
    fileFilteredFiles = fileAutocompleteFiles.filter(f =>
        q === '' || f.name.toLowerCase().includes(q) || (f.rel_path && f.rel_path.toLowerCase().includes(q))
    );

    // Sort: exact name prefix first, then rel_path prefix, then contains
    if (q) {
        fileFilteredFiles.sort((a, b) => {
            const aNameStarts = a.name.toLowerCase().startsWith(q) ? 0 : 1;
            const bNameStarts = b.name.toLowerCase().startsWith(q) ? 0 : 1;
            if (aNameStarts !== bNameStarts) return aNameStarts - bNameStarts;
            const aPathStarts = (a.rel_path || a.name).toLowerCase().startsWith(q) ? 0 : 1;
            const bPathStarts = (b.rel_path || b.name).toLowerCase().startsWith(q) ? 0 : 1;
            if (aPathStarts !== bPathStarts) return aPathStarts - bPathStarts;
            return (a.rel_path || a.name).localeCompare(b.rel_path || b.name);
        });
    }

    // Limit to 30 results to keep dropdown manageable
    fileFilteredFiles = fileFilteredFiles.slice(0, 30);

    fileAutocompleteIndex = 0;
    renderAutocomplete();

    fileAutocompleteEl.style.display = 'block';
    fileAutocompleteVisible = true;
}

function hideFileAutocomplete() {
    fileAutocompleteEl.style.display = 'none';
    fileAutocompleteVisible = false;
    fileAutocompleteIndex = 0;
    fileFilteredFiles = [];
    // Clear cache so next @ trigger gets fresh file list
    fileAutocompleteFetchCache = null;
}

function renderAutocomplete() {
    if (fileFilteredFiles.length === 0) {
        fileAutocompleteEl.innerHTML = `
            <div class="file-autocomplete-header">Files in current directory</div>
            <div class="file-autocomplete-empty">No files found</div>
        `;
        return;
    }

    const cwd = fileAutocompleteFetchCache ? fileAutocompleteFetchCache.cwd : '';
    let html = `<div class="file-autocomplete-header">Files in ${escapeHtml(cwd)}</div>`;
    fileFilteredFiles.forEach((file, i) => {
        const icon = file.type === 'directory' ? '\uD83D\uDCC1' : '\uD83D\uDCC4';
        const activeClass = i === fileAutocompleteIndex ? ' active' : '';
        const badge = file.type === 'directory' ? 'folder' : file.name.split('.').pop();
        const relPath = file.rel_path || file.name;
        // Show folder path only if file is inside a subfolder
        const folderPath = relPath.includes('/') ? relPath.substring(0, relPath.lastIndexOf('/')) : '';
        html += `
            <div class="file-autocomplete-item${activeClass}" data-index="${i}">
                <span class="file-icon">${icon}</span>
                <span class="file-name">${escapeHtml(file.name)}</span>
                ${folderPath ? `<span class="file-folder-path">${escapeHtml(folderPath)}</span>` : ''}
                <span class="file-type-badge">${escapeHtml(badge)}</span>
            </div>
        `;
    });

    fileAutocompleteEl.innerHTML = html;

    // Add click handlers
    fileAutocompleteEl.querySelectorAll('.file-autocomplete-item').forEach(item => {
        item.addEventListener('mousedown', (e) => {
            e.preventDefault(); // prevent textarea blur
            const idx = parseInt(item.dataset.index, 10);
            selectFileAutocompleteItem(idx);
        });
    });
}

function updateAutocompleteHighlight() {
    const items = fileAutocompleteEl.querySelectorAll('.file-autocomplete-item');
    items.forEach((item, i) => {
        item.classList.toggle('active', i === fileAutocompleteIndex);
    });
    // Scroll active item into view
    if (items[fileAutocompleteIndex]) {
        items[fileAutocompleteIndex].scrollIntoView({ block: 'nearest' });
    }
}

function selectFileAutocompleteItem(index) {
    if (index < 0 || index >= fileFilteredFiles.length) return;

    const file = fileFilteredFiles[index];
    const text = messageInput.value;
    const cursorPos = messageInput.selectionStart;

    // Replace @query with @filename
    const before = text.substring(0, fileAtTriggerPos);
    const after = text.substring(cursorPos);
    const insertion = '@' + file.name + ' ';
    messageInput.value = before + insertion + after;

    // Set cursor after inserted text
    const newPos = fileAtTriggerPos + insertion.length;
    messageInput.selectionStart = newPos;
    messageInput.selectionEnd = newPos;

    hideFileAutocomplete();
    messageInput.focus();
    messageInput.dispatchEvent(new Event('input')); // trigger resize
}

// Close autocomplete when clicking outside
document.addEventListener('mousedown', (e) => {
    if (fileAutocompleteVisible &&
        !fileAutocompleteEl.contains(e.target) &&
        e.target !== messageInput) {
        hideFileAutocomplete();
    }
});

