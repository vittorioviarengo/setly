/**
 * Custom Dialog Box Component
 * A modern, accessible replacement for browser alert(), confirm(), and prompt()
 */

class AppDialog {
    constructor() {
        this.overlay = null;
        this.dialog = null;
        this.currentCallback = null;
        this.init();
    }

    init() {
        // Create dialog HTML structure
        const overlay = document.createElement('div');
        overlay.className = 'app-dialog-overlay';
        overlay.innerHTML = `
            <div class="app-dialog">
                <div class="app-dialog-header">
                    <h2 class="app-dialog-title">
                        <span class="app-dialog-icon"></span>
                        <span class="app-dialog-title-text"></span>
                    </h2>
                </div>
                <div class="app-dialog-body"></div>
                <div class="app-dialog-footer"></div>
            </div>
        `;
        
        // Wait for body to be ready
        if (document.body) {
            document.body.appendChild(overlay);
        } else {
            document.addEventListener('DOMContentLoaded', () => {
                document.body.appendChild(overlay);
            });
        }
        
        this.overlay = overlay;
        this.dialog = overlay.querySelector('.app-dialog');
        
        // Close on overlay click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                this.close();
            }
        });
        
        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.overlay.classList.contains('active')) {
                this.close();
            }
        });
    }

    /**
     * Show an alert dialog
     * @param {string} message - The message to display
     * @param {string} type - Type: 'info', 'success', 'warning', 'error' (default: 'info')
     * @param {string} title - Optional custom title
     */
    alert(message, type = 'info', title = null) {
        const icons = {
            info: 'ℹ️',
            success: '✓',
            warning: '⚠️',
            error: '✕',
            question: '?'
        };
        
        const titles = {
            info: 'Information',
            success: 'Success',
            warning: 'Warning',
            error: 'Error',
            question: 'Question'
        };
        
        this.show({
            title: title || titles[type] || titles.info,
            message: message,
            icon: icons[type] || icons.info,
            iconClass: type,
            buttons: [
                { text: 'OK', class: 'primary', callback: () => this.close() }
            ]
        });
    }

    /**
     * Show a confirmation dialog
     * @param {string} message - The message to display
     * @param {function} onConfirm - Callback when confirmed
     * @param {function} onCancel - Optional callback when cancelled
     * @param {string} title - Optional custom title
     */
    confirm(message, onConfirm, onCancel = null, title = 'Confirm') {
        this.show({
            title: title,
            message: message,
            icon: '?',
            iconClass: 'question',
            buttons: [
                { 
                    text: 'Cancel', 
                    class: 'secondary', 
                    callback: () => {
                        this.close();
                        if (onCancel) onCancel();
                    }
                },
                { 
                    text: 'Confirm', 
                    class: 'primary', 
                    callback: () => {
                        this.close();
                        if (onConfirm) onConfirm();
                    }
                }
            ]
        });
    }

    /**
     * Show a confirmation dialog with danger action
     * @param {string} message - The message to display
     * @param {function} onConfirm - Callback when confirmed
     * @param {function} onCancel - Optional callback when cancelled
     * @param {string} confirmText - Text for confirm button (default: 'Delete')
     * @param {string} title - Optional custom title
     */
    confirmDanger(message, onConfirm, onCancel = null, confirmText = 'Delete', title = 'Confirm Action') {
        this.show({
            title: title,
            message: message,
            icon: '⚠️',
            iconClass: 'warning',
            buttons: [
                { 
                    text: 'Cancel', 
                    class: 'secondary', 
                    callback: () => {
                        this.close();
                        if (onCancel) onCancel();
                    }
                },
                { 
                    text: confirmText, 
                    class: 'danger', 
                    callback: () => {
                        this.close();
                        if (onConfirm) onConfirm();
                    }
                }
            ]
        });
    }

    /**
     * Generic show method
     * @param {object} options - Dialog options
     */
    show(options) {
        const { title, message, icon, iconClass, buttons } = options;
        
        // Ensure dialog is in DOM (defensive check)
        if (!this.dialog || !this.dialog.parentNode) {
            console.error('Dialog not initialized or not in DOM. Re-initializing...');
            this.init();
        }
        
        // Set title
        const titleElement = this.dialog.querySelector('.app-dialog-title-text');
        if (titleElement) {
            titleElement.textContent = title;
        }
        
        // Set icon
        const iconElement = this.dialog.querySelector('.app-dialog-icon');
        if (iconElement) {
            iconElement.textContent = icon;
            iconElement.className = `app-dialog-icon ${iconClass}`;
        }
        
        // Set message
        const bodyElement = this.dialog.querySelector('.app-dialog-body');
        if (bodyElement) {
            bodyElement.innerHTML = message;
        }
        
        // Set buttons
        const footerElement = this.dialog.querySelector('.app-dialog-footer');
        if (footerElement) {
            footerElement.innerHTML = '';
            
            buttons.forEach((button, index) => {
                const btn = document.createElement('button');
                btn.className = `app-dialog-btn ${button.class}`;
                btn.textContent = button.text;
                btn.onclick = button.callback;
                
                // Focus first primary button
                if (button.class.includes('primary') && index === buttons.length - 1) {
                    setTimeout(() => btn.focus(), 100);
                }
                
                footerElement.appendChild(btn);
            });
        }
        
        // Show overlay
        if (this.overlay) {
            this.overlay.classList.add('active');
        }
        document.body.style.overflow = 'hidden';
    }

    close() {
        this.overlay.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDialog);
} else {
    initializeDialog();
}

function initializeDialog() {
    // Create global instance
    window.appDialog = new AppDialog();

    // Create convenient global functions that mimic native alert/confirm
    window.showAlert = (message, type = 'info', title = null) => {
        window.appDialog.alert(message, type, title);
    };

    window.showConfirm = (message, onConfirm, onCancel = null, title = 'Confirm') => {
        window.appDialog.confirm(message, onConfirm, onCancel, title);
    };

    window.showConfirmDanger = (message, onConfirm, onCancel = null, confirmText = 'Delete', title = 'Confirm Action') => {
        window.appDialog.confirmDanger(message, onConfirm, onCancel, confirmText, title);
    };
}

