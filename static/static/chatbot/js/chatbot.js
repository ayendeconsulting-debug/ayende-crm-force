/**
 * AyendeCX Chatbot Widget
 * Enhanced with End Chat functionality and formatted text support
 */
// Google Analytics tracking helper
function trackChatbotEvent(action, label) {
    if (typeof gtag !== 'undefined') {
        gtag('event', action, {
            'event_category': 'chatbot',
            'event_label': label || ''
        });
    }
}

class ChatbotWidget {
    constructor(config) {
        this.config = config;
        this.sessionId = null;
        this.isMinimized = true;
        this.isInitialized = false;

        this.init();
    }

    init() {
        this.container = document.getElementById('chatbot-container');
        this.toggle = document.getElementById('chatbot-toggle');
        this.minimize = document.getElementById('chatbot-minimize');
        this.endChat = document.getElementById('chatbot-end');
        this.form = document.getElementById('chatbot-form');
        this.input = document.getElementById('chatbot-input');
        this.messagesContainer = document.getElementById('chatbot-messages');
        this.typingIndicator = document.getElementById('chatbot-typing-indicator');

        this.attachEventListeners();
        this.loadSessionFromStorage();
    }

    attachEventListeners() {
        // Toggle chat window
        this.toggle.addEventListener('click', () => {
            this.toggleChat();
        });

        // Minimize chat
        this.minimize.addEventListener('click', () => {
            this.minimizeChat();
        });

        // End chat
        this.endChat.addEventListener('click', () => {
            this.endChatSession();
        });

        // Send message
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });

        // Auto-resize input
        this.input.addEventListener('input', () => {
            this.input.style.height = 'auto';
            this.input.style.height = this.input.scrollHeight + 'px';
        });
    }

    toggleChat() {
        if (this.isMinimized) {
            this.openChat();
        } else {
            this.minimizeChat();
        }
    }

    async openChat() {
        this.container.classList.add('open');
        this.toggle.classList.remove('hidden');
        this.isMinimized = false;

        trackChatbotEvent('chatbot_opened', 'Omoh');

        // Initialize session if not already done
        if (!this.isInitialized) {
            await this.initializeSession();
        }

        // Focus input
        setTimeout(() => {
            this.input.focus();
        }, 300);
    }

    minimizeChat() {
        this.container.classList.remove('open');
        this.toggle.classList.remove('hidden');
        this.isMinimized = true;
    }

    async endChatSession() {
        if (!confirm('Are you sure you want to end this chat? Your conversation history will be cleared.')) {
            return;
        }

        // Close session on server
        await this.closeSession();

        // Clear messages
        this.messagesContainer.innerHTML = '';

        // Add "Chat Ended" message
        this.addMessage('Chat ended. Feel free to start a new conversation anytime!', 'system');

        // Reset state
        this.sessionId = null;
        this.isInitialized = false;

        trackChatbotEvent('chat_ended', 'User ended chat');

        // Minimize chat after a brief delay
        setTimeout(() => {
            this.minimizeChat();
        }, 2000);
    }

    async initializeSession() {
        try {
            const response = await fetch(`${this.config.apiBase}/${this.config.subdomain}/init/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    visitor_info: this.getVisitorInfo()
                })
            });

            const data = await response.json();

            if (data.success) {
                this.sessionId = data.session_id;
                this.saveSessionToStorage();

                // Display welcome message
                this.addMessage(data.welcome_message, 'bot');

                this.isInitialized = true;
            } else {
                this.showError('Failed to start chat. Please try again.');
            }
        } catch (error) {
            console.error('Error initializing chat:', error);
            this.showError('Failed to connect. Please check your internet connection.');
        }
    }

    async sendMessage() {
        const message = this.input.value.trim();

        if (!message) return;

        // Add user message to chat
        this.addMessage(message, 'user');

        // Clear input
        this.input.value = '';
        this.input.style.height = 'auto';

        // Show typing indicator
        this.showTypingIndicator();

        try {
            const response = await fetch(`${this.config.apiBase}/${this.config.subdomain}/message/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    message: message,
                    visitor_info: this.getVisitorInfo()
                })
            });

            const data = await response.json();

            this.hideTypingIndicator();

            if (data.success) {
                // Add bot response
                this.addMessage(data.message, 'bot');
                trackChatbotEvent('message_sent', message);
            } else {
                this.showError('Failed to send message. Please try again.');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.hideTypingIndicator();
            this.showError('Failed to send message. Please check your connection.');
        }
    }

    addMessage(text, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';

        // Apply inline styles to ensure colors work (bypass CSS cache)
        if (type === 'bot') {
            bubble.style.backgroundColor = '#374151';
            bubble.style.color = '#F3F4F6';
        } else if (type === 'user') {
            bubble.style.backgroundColor = '#1E40AF';
            bubble.style.color = '#FFFFFF';
        } else if (type === 'system') {
            bubble.style.backgroundColor = '#1F2937';
            bubble.style.color = '#60A5FA';
            bubble.style.fontStyle = 'italic';
            bubble.style.textAlign = 'center';
            bubble.style.border = '1px solid #3B82F6';
        }

        // Format text with line breaks and preserve structure
        bubble.innerHTML = this.formatMessage(text);

        const timestamp = document.createElement('div');
        timestamp.className = 'message-timestamp';
        timestamp.textContent = this.formatTime(new Date());

        messageDiv.appendChild(bubble);
        messageDiv.appendChild(timestamp);

        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatMessage(text) {
        // Escape HTML to prevent XSS attacks
        const escapeHtml = (unsafe) => {
            return unsafe
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        };

        // Escape the text first
        let formatted = escapeHtml(text);

        // Convert line breaks to <br>
        formatted = formatted.replace(/\n/g, '<br>');

        // Convert bullet points (- or •) at start of line to styled bullets
        formatted = formatted.replace(/^[-•]\s/gm, '<span style="margin-left: 8px;">• </span>');
        formatted = formatted.replace(/<br>[-•]\s/g, '<br><span style="margin-left: 8px;">• </span>');

        return formatted;
    }

    showTypingIndicator() {
        this.typingIndicator.style.display = 'block';
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        this.typingIndicator.style.display = 'none';
    }

    showError(message) {
        this.addMessage(message, 'system');
    }

    scrollToBottom() {
        setTimeout(() => {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }, 100);
    }

    formatTime(date) {
        return date.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    }

    getVisitorInfo() {
        // You can collect visitor info here
        return {
            // visitor_email: ...,
            // visitor_name: ...,
            // visitor_phone: ...
        };
    }

    saveSessionToStorage() {
        if (this.sessionId) {
            sessionStorage.setItem('chatbot_session_id', this.sessionId);
        }
    }

    loadSessionFromStorage() {
        const storedSessionId = sessionStorage.getItem('chatbot_session_id');
        if (storedSessionId) {
            this.sessionId = storedSessionId;
            this.isInitialized = true;
        }
    }

    async closeSession() {
        if (!this.sessionId) return;

        try {
            await fetch(`${this.config.apiBase}/${this.config.subdomain}/close/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            });

            sessionStorage.removeItem('chatbot_session_id');
        } catch (error) {
            console.error('Error closing session:', error);
        }
    }
}

// Initialize chatbot when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.chatbot = new ChatbotWidget(window.CHATBOT_CONFIG);
    });
} else {
    window.chatbot = new ChatbotWidget(window.CHATBOT_CONFIG);
}

// Close session when user leaves
window.addEventListener('beforeunload', () => {
    if (window.chatbot) {
        window.chatbot.closeSession();
    }
});
