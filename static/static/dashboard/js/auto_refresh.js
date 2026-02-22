// CRM Dashboard Auto-Refresh
// Refreshes data every 5 minutes without reloading page

(function() {
    'use strict';
    
    const REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes in milliseconds
    let refreshTimer;
    let isRefreshing = false;
    
    // Sections to update (add class names of sections that should refresh)
    const REFRESH_SELECTORS = [
        '.stats-card',           // Statistics cards
        '.customer-list',        // Customer tables
        '.transaction-list',     // Transaction tables
        'table tbody',           // Table bodies
        '.dashboard-stats',      // Dashboard statistics
        '.card-body',            // Card contents
        '[data-auto-refresh]'    // Any element with this attribute
    ];
    
    // Don't refresh if user is interacting
    function isUserActive() {
        // Check if any input has focus
        const activeElement = document.activeElement;
        if (activeElement && (
            activeElement.tagName === 'INPUT' || 
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.tagName === 'SELECT' ||
            activeElement.isContentEditable
        )) {
            return true;
        }
        return false;
    }
    
    // Show refresh indicator
    function showRefreshIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'refresh-indicator';
        indicator.style.cssText = `
            position: fixed;
            top: 70px;
            right: 20px;
            background: #667eea;
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            z-index: 9999;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 10px;
        `;
        indicator.innerHTML = `
            <svg width="16" height="16" fill="currentColor" class="spin">
                <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="2" fill="none" 
                        stroke-dasharray="40" stroke-dashoffset="10"/>
            </svg>
            <span>Auto-refresh every 5 min</span>
        `;
        
        // Add spin animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            .spin { animation: spin 1s linear infinite; }
        `;
        document.head.appendChild(style);
        
        document.body.appendChild(indicator);
        
        // Remove after 3 seconds
        setTimeout(() => {
            if (indicator.parentNode) {
                indicator.style.opacity = '0';
                indicator.style.transition = 'opacity 0.3s';
                setTimeout(() => indicator.remove(), 300);
            }
        }, 3000);
    }
    
    // Refresh data
    async function refreshData() {
        // Skip if already refreshing or user is active
        if (isRefreshing || isUserActive()) {
            console.log('[Auto-Refresh] Skipped - user active or already refreshing');
            return;
        }
        
        isRefreshing = true;
        console.log('[Auto-Refresh] Starting data refresh...');
        showRefreshIndicator();
        
        try {
            // Fetch current page
            const response = await fetch(window.location.href, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const html = await response.text();
            const parser = new DOMParser();
            const newDoc = parser.parseFromString(html, 'text/html');
            
            // Update each section
            let updatedCount = 0;
            REFRESH_SELECTORS.forEach(selector => {
                const oldElements = document.querySelectorAll(selector);
                const newElements = newDoc.querySelectorAll(selector);
                
                oldElements.forEach((oldEl, index) => {
                    if (newElements[index]) {
                        // Preserve scroll position
                        const scrollTop = oldEl.scrollTop;
                        
                        // Update content
                        oldEl.innerHTML = newElements[index].innerHTML;
                        
                        // Restore scroll
                        oldEl.scrollTop = scrollTop;
                        
                        updatedCount++;
                    }
                });
            });
            
            console.log(`[Auto-Refresh] Updated ${updatedCount} sections`);
            
        } catch (error) {
            console.error('[Auto-Refresh] Error:', error);
        } finally {
            isRefreshing = false;
        }
    }
    
    // Start auto-refresh
    function startAutoRefresh() {
        console.log('[Auto-Refresh] Enabled - refreshing every 5 minutes');
        
        // Initial refresh after 5 minutes
        refreshTimer = setInterval(refreshData, REFRESH_INTERVAL);
        
        // Also refresh when page becomes visible again (after tab switch)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && !isRefreshing) {
                console.log('[Auto-Refresh] Page visible - checking for updates');
                refreshData();
            }
        });
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startAutoRefresh);
    } else {
        startAutoRefresh();
    }
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (refreshTimer) {
            clearInterval(refreshTimer);
        }
    });
})();
