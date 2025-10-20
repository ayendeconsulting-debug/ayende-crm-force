/* MODERN ADMIN DASHBOARD CUSTOM JAVASCRIPT */
/* Save as: static/admin/js/custom-admin.js */

(function() {
    'use strict';

    // Wait for DOM to be ready
    document.addEventListener('DOMContentLoaded', function() {
        
        // Initialize all features
        initDashboardStats();
        initTableEnhancements();
        initFormEnhancements();
        initSearchEnhancements();
        initAnimations();
        initTooltips();
        
    });

    /**
     * Dashboard Statistics Cards
     */
    function initDashboardStats() {
        // Add dashboard stats to the admin index page
        const contentHeader = document.querySelector('.content-header');
        if (contentHeader && window.location.pathname === '/admin/') {
            const statsHTML = `
                <div class="dashboard-stats">
                    <div class="stat-card success">
                        <div class="stat-value" id="total-tenants">0</div>
                        <div class="stat-label">Active Tenants</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="total-customers">0</div>
                        <div class="stat-label">Total Customers</div>
                    </div>
                    <div class="stat-card warning">
                        <div class="stat-value" id="total-transactions">0</div>
                        <div class="stat-label">Transactions Today</div>
                    </div>
                    <div class="stat-card danger">
                        <div class="stat-value" id="total-revenue">$0</div>
                        <div class="stat-label">Revenue Today</div>
                    </div>
                </div>
            `;
            contentHeader.insertAdjacentHTML('afterend', statsHTML);
            
            // Animate counters
            animateCounters();
        }
    }

    /**
     * Animate number counters
     */
    function animateCounters() {
        const counters = document.querySelectorAll('.stat-value');
        
        counters.forEach(counter => {
            const target = parseInt(counter.textContent) || 0;
            const duration = 1000; // 1 second
            const increment = target / (duration / 16); // 60fps
            let current = 0;
            
            const updateCounter = () => {
                current += increment;
                if (current < target) {
                    counter.textContent = Math.ceil(current);
                    requestAnimationFrame(updateCounter);
                } else {
                    counter.textContent = target;
                }
            };
            
            updateCounter();
        });
    }

    /**
     * Enhanced Table Features
     */
    function initTableEnhancements() {
        // Add row click handlers
        const tableRows = document.querySelectorAll('tbody tr');
        tableRows.forEach(row => {
            // Make entire row clickable
            const link = row.querySelector('a');
            if (link) {
                row.style.cursor = 'pointer';
                row.addEventListener('click', function(e) {
                    if (e.target.tagName !== 'A' && e.target.tagName !== 'INPUT') {
                        link.click();
                    }
                });
            }
            
            // Add fade-in animation
            row.classList.add('fade-in');
        });

        // Add sorting indicators
        const tableHeaders = document.querySelectorAll('thead th a');
        tableHeaders.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', function() {
                // Add loading state
                document.body.classList.add('loading');
            });
        });
    }

    /**
     * Form Enhancements
     */
    function initFormEnhancements() {
        // Auto-focus first input
        const firstInput = document.querySelector('form input:not([type="hidden"]):not([type="submit"])');
        if (firstInput) {
            firstInput.focus();
        }

        // Add character counter to textareas
        const textareas = document.querySelectorAll('textarea');
        textareas.forEach(textarea => {
            const maxLength = textarea.getAttribute('maxlength');
            if (maxLength) {
                const counter = document.createElement('div');
                counter.className = 'character-counter';
                counter.style.cssText = 'text-align: right; font-size: 0.875rem; color: #64748b; margin-top: 4px;';
                counter.textContent = `0 / ${maxLength}`;
                
                textarea.parentNode.insertBefore(counter, textarea.nextSibling);
                
                textarea.addEventListener('input', function() {
                    const length = this.value.length;
                    counter.textContent = `${length} / ${maxLength}`;
                    
                    if (length > maxLength * 0.9) {
                        counter.style.color = '#ef4444';
                    } else {
                        counter.style.color = '#64748b';
                    }
                });
            }
        });

        // Add real-time validation
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
            inputs.forEach(input => {
                input.addEventListener('blur', function() {
                    if (!this.value) {
                        this.style.borderColor = '#ef4444';
                    } else {
                        this.style.borderColor = '#10b981';
                    }
                });
            });
        });

        // Confirm delete actions
        const deleteButtons = document.querySelectorAll('input[name="_delete"], .deletelink');
        deleteButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                if (!confirm('Are you sure you want to delete this item? This action cannot be undone.')) {
                    e.preventDefault();
                    return false;
                }
            });
        });
    }

    /**
     * Enhanced Search
     */
    function initSearchEnhancements() {
        const searchInputs = document.querySelectorAll('input[type="search"], input#searchbar');
        
        searchInputs.forEach(input => {
            // Add search icon
            const icon = document.createElement('span');
            icon.innerHTML = '🔍';
            icon.style.cssText = 'position: absolute; right: 12px; top: 50%; transform: translateY(-50%); pointer-events: none;';
            
            if (input.parentNode.style.position !== 'relative') {
                input.parentNode.style.position = 'relative';
            }
            input.parentNode.appendChild(icon);
            
            // Add live search indicator
            let searchTimeout;
            input.addEventListener('input', function() {
                clearTimeout(searchTimeout);
                icon.innerHTML = '⏳';
                
                searchTimeout = setTimeout(() => {
                    icon.innerHTML = '🔍';
                }, 500);
            });
        });
    }

    /**
     * Scroll Animations
     */
    function initAnimations() {
        const animateElements = document.querySelectorAll('.bg-white, .stat-card, tbody tr');
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('fade-in');
                }
            });
        }, {
            threshold: 0.1
        });
        
        animateElements.forEach(element => {
            observer.observe(element);
        });
    }

    /**
     * Tooltips
     */
    function initTooltips() {
        const tooltipElements = document.querySelectorAll('[title]');
        
        tooltipElements.forEach(element => {
            const title = element.getAttribute('title');
            if (title) {
                // Create custom tooltip
                element.addEventListener('mouseenter', function(e) {
                    const tooltip = document.createElement('div');
                    tooltip.className = 'custom-tooltip';
                    tooltip.textContent = title;
                    tooltip.style.cssText = `
                        position: absolute;
                        background: #1e293b;
                        color: white;
                        padding: 8px 12px;
                        border-radius: 6px;
                        font-size: 0.875rem;
                        z-index: 9999;
                        pointer-events: none;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
                    `;
                    
                    document.body.appendChild(tooltip);
                    
                    const rect = element.getBoundingClientRect();
                    tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
                    tooltip.style.top = rect.top - tooltip.offsetHeight - 8 + 'px';
                    
                    element.addEventListener('mouseleave', function() {
                        tooltip.remove();
                    }, { once: true });
                });
            }
        });
    }

    /**
     * Keyboard Shortcuts
     */
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K: Focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.querySelector('input[type="search"], input#searchbar');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
        
        // Ctrl/Cmd + S: Save form
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            const submitButton = document.querySelector('input[type="submit"], button[type="submit"]');
            if (submitButton) {
                submitButton.click();
            }
        }
        
        // Escape: Clear search
        if (e.key === 'Escape') {
            const searchInput = document.querySelector('input[type="search"], input#searchbar');
            if (searchInput && searchInput === document.activeElement) {
                searchInput.value = '';
                searchInput.blur();
            }
        }
    });

    /**
     * Auto-save drafts (for long forms)
     */
    function initAutoSave() {
        const forms = document.querySelectorAll('form');
        
        forms.forEach(form => {
            const inputs = form.querySelectorAll('input, textarea, select');
            const formId = form.getAttribute('id') || 'admin-form';
            
            // Load saved data
            const savedData = localStorage.getItem(`autosave-${formId}`);
            if (savedData) {
                const data = JSON.parse(savedData);
                Object.keys(data).forEach(name => {
                    const input = form.querySelector(`[name="${name}"]`);
                    if (input && !input.value) {
                        input.value = data[name];
                        input.style.background = '#fef3c7'; // Highlight restored fields
                    }
                });
            }
            
            // Save on change
            inputs.forEach(input => {
                input.addEventListener('change', function() {
                    const formData = {};
                    inputs.forEach(inp => {
                        if (inp.name) {
                            formData[inp.name] = inp.value;
                        }
                    });
                    localStorage.setItem(`autosave-${formId}`, JSON.stringify(formData));
                });
            });
            
            // Clear on submit
            form.addEventListener('submit', function() {
                localStorage.removeItem(`autosave-${formId}`);
            });
        });
    }

    /**
     * Loading indicators
     */
    function showLoading(element) {
        element.classList.add('loading');
    }

    function hideLoading(element) {
        element.classList.remove('loading');
    }

    // Export functions for use elsewhere
    window.adminDashboard = {
        showLoading,
        hideLoading,
        animateCounters
    };

})();