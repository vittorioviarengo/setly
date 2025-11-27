/**
 * Tip Dialog Component
 * Dialog per richiesta canzone con contributi opzionali
 */

class TipDialog {
    constructor() {
        this.overlay = null;
        this.dialog = null;
        this.currentSong = null;
        this.currentUsername = null;
        this.selectedTipAmount = null;
        this.tipIntent = null;
        this.requestCount = 0;
        this.init();
        this.loadSessionData();
    }

    init() {
        // Create dialog HTML structure
        const overlay = document.createElement('div');
        overlay.className = 'tip-dialog-overlay';
        overlay.id = 'tipDialogOverlay';
        
        const dialog = document.createElement('div');
        dialog.className = 'tip-dialog';
        dialog.id = 'tipDialog';
        
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);
        
        this.overlay = overlay;
        this.dialog = dialog;
        
        // Close on overlay click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                this.close();
            }
        });
    }

    loadSessionData() {
        // Load request count from sessionStorage
        const count = sessionStorage.getItem('songRequestsCount');
        this.requestCount = count ? parseInt(count, 10) : 0;
    }

    incrementRequestCount() {
        this.requestCount++;
        sessionStorage.setItem('songRequestsCount', this.requestCount.toString());
    }

    showRequestDialog(song, username, musicianName) {
        this.currentSong = song;
        this.currentUsername = username;
        this.selectedTipAmount = null;
        this.tipIntent = null;

        // Never pre-select a tip amount - always start with no selection
        // User can optionally select a tip if they want
        const preSelectedAmount = null;

        // Get tip enabled status from active gig
        this.checkTipEnabled().then(tipEnabled => {
            const dialogHTML = `
                <div class="tip-dialog-header">
                    <h2 class="tip-dialog-title">${this.escapeHtml(song.title)}</h2>
                    <button class="tip-dialog-close" aria-label="Close">&times;</button>
                </div>
                <div class="tip-dialog-body">
                    ${song.image ? `<img src="${this.escapeHtml(song.image)}" alt="${this.escapeHtml(song.title)}" class="tip-dialog-song-image">` : ''}
                    <div class="tip-dialog-song-info">
                        <div class="tip-dialog-artist">${this.escapeHtml(song.author)}</div>
                    </div>
                    
                    <div class="tip-dialog-message">
                        <p><strong>La richiesta è gratuita.</strong></p>
                        ${tipEnabled ? `<p>Se vuoi, puoi aggiungere una mancia per <strong>${this.escapeHtml(musicianName)}</strong>.</p>` : ''}
                    </div>

                    ${tipEnabled ? `
                    <div class="tip-dialog-tip-section">
                        <label class="tip-dialog-label">Mancia (opzionale)</label>
                        <div class="tip-amount-chips">
                            <button class="tip-chip ${preSelectedAmount === 2 ? 'selected' : ''}" data-amount="2" data-label="Grazie">
                                2 €<br><small>Grazie</small>
                            </button>
                            <button class="tip-chip ${preSelectedAmount === 5 ? 'selected' : ''}" data-amount="5" data-label="Offri un drink">
                                5 €<br><small>Offri un drink</small>
                            </button>
                            <button class="tip-chip ${preSelectedAmount === 10 ? 'selected' : ''}" data-amount="10" data-label="Serata speciale">
                                10 €<br><small>Serata speciale</small>
                            </button>
                            <button class="tip-chip tip-chip-custom" data-amount="custom">
                                Altro
                            </button>
                        </div>
                        <div class="tip-custom-amount" id="tipCustomAmount" style="display: none;">
                            <input type="number" id="customTipInput" placeholder="Importo in €" min="1" step="0.50">
                        </div>
                    </div>

                    <div class="tip-dialog-payment-info">
                        <p>💳 Pagherai con PayPal al passo successivo.</p>
                    </div>
                    ` : ''}

                    <div class="tip-dialog-actions">
                        <button class="tip-dialog-btn tip-dialog-btn-secondary" id="tipDialogCancel">Annulla</button>
                        <button class="tip-dialog-btn tip-dialog-btn-primary" id="tipDialogSubmit">
                            ${this.selectedTipAmount ? `Invia richiesta + mancia ${this.selectedTipAmount} €` : 'Invia richiesta'}
                        </button>
                    </div>
                </div>
            `;

            this.dialog.innerHTML = dialogHTML;

            // Setup event listeners
            this.setupRequestDialogListeners(tipEnabled);
            
            // Show dialog
            this.show();
        });
    }

    setupRequestDialogListeners(tipEnabled) {
        // Close button
        const closeBtn = this.dialog.querySelector('.tip-dialog-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.close());
        }

        // Cancel button
        const cancelBtn = this.dialog.querySelector('#tipDialogCancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.close());
        }

        if (tipEnabled) {
            // Tip amount chips
            const chips = this.dialog.querySelectorAll('.tip-chip');
            chips.forEach(chip => {
                chip.addEventListener('click', () => {
                    chips.forEach(c => c.classList.remove('selected'));
                    chip.classList.add('selected');
                    
                    const amount = chip.dataset.amount;
                    console.log('💳 Tip chip clicked, amount:', amount);
                    if (amount === 'custom') {
                        document.getElementById('tipCustomAmount').style.display = 'block';
                        document.getElementById('customTipInput').focus();
                        this.selectedTipAmount = null;
                        console.log('Custom tip selected, waiting for input');
                    } else {
                        document.getElementById('tipCustomAmount').style.display = 'none';
                        this.selectedTipAmount = parseFloat(amount);
                        console.log('Tip amount selected:', this.selectedTipAmount, '€');
                        this.updateSubmitButton();
                    }
                });
            });

            // Custom amount input
            const customInput = document.getElementById('customTipInput');
            if (customInput) {
                customInput.addEventListener('input', (e) => {
                    const value = parseFloat(e.target.value);
                    if (value && value >= 1) {
                        this.selectedTipAmount = value;
                        this.updateSubmitButton();
                    } else {
                        this.selectedTipAmount = null;
                        this.updateSubmitButton();
                    }
                });
            }
        }

        // Submit button
        const submitBtn = this.dialog.querySelector('#tipDialogSubmit');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => this.submitRequest());
        }
    }

    updateSubmitButton() {
        const submitBtn = this.dialog.querySelector('#tipDialogSubmit');
        if (submitBtn) {
            if (this.selectedTipAmount) {
                submitBtn.textContent = `Invia richiesta + mancia ${this.selectedTipAmount} €`;
            } else {
                submitBtn.textContent = 'Invia richiesta';
            }
        }
    }

    async checkTipEnabled() {
        try {
            // Get tenant slug from URL
            const path = window.location.pathname;
            const match = path.match(/\/([^\/]+)\//);
            const tenantSlug = match ? match[1] : '';
            
            if (!tenantSlug) return true; // Default to enabled
            
            const response = await fetch(`/${tenantSlug}/get_active_gig`);
            const data = await response.json();
            
            if (data.success && data.gig) {
                return data.gig.tip_enabled !== false;
            }
            return true; // Default to enabled if no gig
        } catch (e) {
            console.error('Error checking tip enabled:', e);
            return true; // Default to enabled on error
        }
    }

    async submitRequest() {
        // Check if we have a valid song
        if (!this.currentSong || !this.currentSong.id) {
            this.showError('Errore: canzone non valida');
            return;
        }

        console.log('📤 Submitting request, selectedTipAmount:', this.selectedTipAmount);

        const submitBtn = this.dialog.querySelector('#tipDialogSubmit');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Invio in corso...';
        }

        try {
            const requestData = {
                user: this.currentUsername
            };

            if (this.selectedTipAmount) {
                // Ensure tip_amount is a number, not a string
                requestData.tip_amount = parseFloat(this.selectedTipAmount);
                console.log('💰 Sending tip_amount:', requestData.tip_amount, 'type:', typeof requestData.tip_amount);
            } else {
                console.log('ℹ️ No tip amount selected');
            }
            
            console.log('📦 Request data to send:', requestData);

            const response = await fetch(`/request_song/${this.currentSong.id}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });

            const data = await response.json();
            
            // Log full response for debugging
            console.log('Full response from /request_song:', {
                status: response.status,
                ok: response.ok,
                data: data,
                has_tip_intent: !!data.tip_intent,
                tip_intent: data.tip_intent,
                data_keys: Object.keys(data),
                full_data_stringified: JSON.stringify(data, null, 2)
            });

            // Log error details for debugging
            if (!response.ok) {
                console.error('Request failed:', {
                    status: response.status,
                    statusText: response.statusText,
                    data: data,
                    requestData: requestData,
                    errorMessage: data.error || data.message || 'Unknown error',
                    fullResponse: JSON.stringify(data, null, 2)
                });
            }

            if (data.redirect) {
                window.location.href = data.redirect;
                return;
            }

            if (!response.ok || !data.success) {
                // Show error message from backend
                const errorMessage = data.error || data.message || `Errore ${response.status}: ${response.statusText}`;
                
                // Special handling for max requests error - show it prominently
                if (errorMessage.includes('massimo di richieste') || errorMessage.includes('Maximum Request')) {
                    this.showError(errorMessage, true); // true = keep dialog open
                } else {
                    this.showError(errorMessage);
                }
                
                if (submitBtn) {
                    submitBtn.disabled = false;
                    this.updateSubmitButton();
                }
                return;
            }

            if (data.success) {
                // Increment request count
                this.incrementRequestCount();

                // Show success message
                const musicianName = window.musicianName || 'il musicista';
                
                console.log('Checking for tip_intent in response:', {
                    has_tip_intent: !!data.tip_intent,
                    tip_intent: data.tip_intent,
                    selectedTipAmount: this.selectedTipAmount,
                    full_data: data
                });
                
                // If there's a tip_intent, proceed to payment step (don't close dialog)
                if (data.tip_intent) {
                    console.log('✅ TipIntent received, proceeding to payment step');
                    this.tipIntent = data.tip_intent;
                    // Store PayPal client ID and mode from response
                    if (data.paypal_client_id) {
                        this.tipIntent.paypal_client_id = data.paypal_client_id;
                    }
                    if (data.paypal_mode) {
                        this.tipIntent.paypal_mode = data.paypal_mode;
                    }
                    console.log('TipIntent after adding PayPal info:', this.tipIntent);
                    // Show success message briefly, then transition to payment step
                    this.showSuccessMessage(`Richiesta inviata a ${musicianName} 🎹`);
                    // Wait a moment then show payment step (dialog stays open)
                    setTimeout(() => {
                        console.log('⏰ Timeout expired, showing payment step...');
                        this.showPaymentStep();
                    }, 1500);
                } else {
                    console.log('❌ No tip_intent in response, closing dialog');
                    // No tip, show message and close
                    this.showSuccessMessage(`Richiesta inviata a ${musicianName} 🎹`);
                    const songId = this.currentSong ? this.currentSong.id : null;
                    setTimeout(() => {
                        this.close();
                        if (songId) {
                            this.onRequestSuccess(songId);
                        }
                    }, 2000);
                }
            }
        } catch (error) {
            console.error('Error submitting request:', error);
            this.showError('Errore: ' + error.message);
            if (submitBtn) {
                submitBtn.disabled = false;
                this.updateSubmitButton();
            }
        }
    }

    showSuccessMessage(message) {
        const body = this.dialog.querySelector('.tip-dialog-body');
        if (body) {
            const successDiv = document.createElement('div');
            successDiv.className = 'tip-dialog-success';
            successDiv.textContent = message;
            body.insertBefore(successDiv, body.firstChild);
        }
    }

    showError(message, keepDialogOpen = false) {
        const body = this.dialog.querySelector('.tip-dialog-body');
        if (body) {
            // Remove any existing error messages
            const existingErrors = body.querySelectorAll('.tip-dialog-error');
            existingErrors.forEach(err => err.remove());
            
            const errorDiv = document.createElement('div');
            errorDiv.className = 'tip-dialog-error';
            errorDiv.innerHTML = `<strong>⚠️ Errore:</strong><br>${message}`;
            body.insertBefore(errorDiv, body.firstChild);
            
            // Scroll to error
            errorDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            
            // Auto-remove after delay (unless it's a max requests error, keep it longer)
            const timeout = message.includes('massimo di richieste') || message.includes('Maximum Request') ? 10000 : 5000;
            setTimeout(() => {
                if (errorDiv.parentNode) {
                    errorDiv.remove();
                }
            }, timeout);
        }
    }

    async showPaymentStep() {
        console.log('showPaymentStep called, tipIntent:', this.tipIntent);
        
        if (!this.tipIntent) {
            console.error('No tipIntent available for payment step');
            this.showError('Errore: dati mancia non disponibili');
            return;
        }
        
        const dialogHTML = `
            <div class="tip-dialog-header">
                <h2 class="tip-dialog-title">Completa la tua mancia con PayPal</h2>
                <button class="tip-dialog-close" aria-label="Close">&times;</button>
            </div>
            <div class="tip-dialog-body">
                <div class="tip-dialog-message">
                    <p>✅ <strong>La richiesta della canzone è già stata inviata.</strong></p>
                    <p>Ora puoi completare la mancia, se vuoi.</p>
                </div>
                
                <div class="tip-dialog-payment-amount">
                    <div class="payment-amount-label">Importo</div>
                    <div class="payment-amount-value">${this.tipIntent.amount_euros.toFixed(2)} €</div>
                </div>

                <div id="paypal-button-container" style="margin: 24px 0; min-height: 200px;"></div>

                <div class="tip-dialog-actions">
                    <button class="tip-dialog-btn tip-dialog-btn-secondary" id="tipDialogSkip">Salta per ora</button>
                </div>
            </div>
        `;

        this.dialog.innerHTML = dialogHTML;

        // Setup listeners
        const closeBtn = this.dialog.querySelector('.tip-dialog-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.showMessage('Mancia annullata. La richiesta della canzone resta attiva.');
                const songId = this.currentSong ? this.currentSong.id : null;
                setTimeout(() => {
                    this.close();
                    if (songId) {
                        this.onRequestSuccess(songId);
                    }
                }, 2000);
            });
        }

        const skipBtn = this.dialog.querySelector('#tipDialogSkip');
        if (skipBtn) {
            skipBtn.addEventListener('click', () => {
                this.showMessage('Mancia annullata. La richiesta della canzone resta attiva.');
                const songId = this.currentSong ? this.currentSong.id : null;
                setTimeout(() => {
                    this.close();
                    if (songId) {
                        this.onRequestSuccess(songId);
                    }
                }, 2000);
            });
        }

        // Initialize PayPal SDK
        await this.initPayPal();
    }

    async initPayPal() {
        try {
            console.log('initPayPal called, tipIntent:', this.tipIntent);
            
            // Get PayPal client ID and mode from tipIntent or fetch from backend
            let paypal_client_id = this.tipIntent.paypal_client_id;
            let paypal_mode = this.tipIntent.paypal_mode || 'sandbox';
            
            // If not in tipIntent, get from backend
            if (!paypal_client_id) {
                console.log('PayPal client ID not in tipIntent, fetching from backend...');
                const response = await fetch('/api/create_paypal_order', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        tip_intent_id: this.tipIntent.id
                    })
                });
                
                const data = await response.json();
                console.log('Backend response for PayPal order:', data);
                if (data.success) {
                    paypal_client_id = data.paypal_client_id;
                    paypal_mode = data.paypal_mode || 'sandbox';
                    // Update tipIntent with order ID if provided
                    if (data.order_id && !this.tipIntent.paypal_order_id) {
                        this.tipIntent.paypal_order_id = data.order_id;
                    }
                } else {
                    throw new Error(data.error || 'Failed to get PayPal credentials');
                }
            }
            
            if (!paypal_client_id) {
                throw new Error('PayPal not configured');
            }
            
            console.log('PayPal client ID:', paypal_client_id, 'Mode:', paypal_mode, 'Order ID:', this.tipIntent.paypal_order_id);

            // Load PayPal SDK if not already loaded
            if (!window.paypal) {
                const script = document.createElement('script');
                script.src = `https://www.paypal.com/sdk/js?client-id=${paypal_client_id}&currency=EUR&intent=capture`;
                script.async = true;
                document.head.appendChild(script);
                
                await new Promise((resolve, reject) => {
                    script.onload = resolve;
                    script.onerror = () => reject(new Error('Failed to load PayPal SDK'));
                    setTimeout(() => reject(new Error('PayPal SDK load timeout')), 10000);
                });
            }

            // Render PayPal buttons
            const container = document.getElementById('paypal-button-container');
            if (container && window.paypal) {
                window.paypal.Buttons({
                    createOrder: async (paypalData, actions) => {
                        // Use the order ID from backend (already created)
                        if (this.tipIntent.paypal_order_id) {
                            // Order already exists, return it
                            return this.tipIntent.paypal_order_id;
                        } else {
                            // Fallback: create order via SDK (shouldn't happen if backend works correctly)
                            return actions.order.create({
                                purchase_units: [{
                                    amount: {
                                        value: this.tipIntent.amount_euros.toFixed(2),
                                        currency_code: this.tipIntent.currency || 'EUR'
                                    },
                                    description: `Mancia per ${window.musicianName || 'il musicista'}`
                                }]
                            });
                        }
                    },
                    onApprove: async (paypalData, actions) => {
                        try {
                            // Capture the order
                            const order = await actions.order.capture();
                            
                            // Confirm payment on backend
                            const confirmResponse = await fetch('/api/tips/paypal/capture', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({
                                    tip_intent_id: this.tipIntent.id,
                                    order_id: order.id
                                })
                            });

                            const confirmData = await confirmResponse.json();
                            
                            if (confirmData.success) {
                                this.showMessage('Grazie per la mancia! 🙌');
                                setTimeout(() => {
                                    this.close();
                                    const songId = this.currentSong ? this.currentSong.id : null;
                                    if (songId) {
                                        this.onRequestSuccess(songId);
                                    }
                                }, 2000);
                            } else {
                                throw new Error(confirmData.error || 'Errore nella conferma pagamento');
                            }
                        } catch (error) {
                            console.error('Payment error:', error);
                            this.showError('Errore nel pagamento: ' + error.message);
                        }
                    },
                    onCancel: () => {
                        this.showMessage('Mancia annullata. La richiesta della canzone resta attiva.');
                        const songId = this.currentSong ? this.currentSong.id : null;
                        setTimeout(() => {
                            this.close();
                            if (songId) {
                                this.onRequestSuccess(songId);
                            }
                        }, 2000);
                    },
                    onError: (err) => {
                        console.error('PayPal error:', err);
                        this.showError('Errore PayPal: ' + (err.message || 'Errore sconosciuto'));
                    }
                }).render('#paypal-button-container');
            } else {
                throw new Error('PayPal container not found or SDK not loaded');
            }
        } catch (error) {
            console.error('Error initializing PayPal:', error);
            this.showError('⚠️ PayPal non è ancora configurato. La mancia è stata registrata ma il pagamento non può essere completato al momento.');
        }
    }


    showMessage(message) {
        const body = this.dialog.querySelector('.tip-dialog-body');
        if (body) {
            const msgDiv = document.createElement('div');
            msgDiv.className = 'tip-dialog-message tip-dialog-info';
            msgDiv.textContent = message;
            body.insertBefore(msgDiv, body.firstChild);
        }
    }

    onRequestSuccess(songId) {
        if (!songId) {
            console.warn('onRequestSuccess called without songId');
            return;
        }

        // Remove song from list
        const songElement = document.querySelector(`[data-song-id="${songId}"]`)?.closest('.song-container, .song-item');
        if (songElement) {
            songElement.style.transition = 'opacity 0.3s ease-out';
            songElement.style.opacity = '0';
            setTimeout(() => {
                songElement.remove();
            }, 300);
        }

        // Add to requested songs
        if (typeof userRequestedSongs !== 'undefined') {
            userRequestedSongs.push(songId);
        }

        // Reload user requests
        if (typeof fetchUserRequests === 'function' && this.currentUsername) {
            fetchUserRequests(this.currentUsername);
        }

        // Show message
        if (typeof showMessage === 'function') {
            showMessage('Richiesta inviata a ' + (window.musicianName || 'il musicista') + ' 🎹');
        }

        // Check for nudge after 2-3 requests
        this.checkNudge();
    }

    checkNudge() {
        // Check if nudge should be shown (after 2-3 requests)
        if (this.requestCount >= 2 && this.requestCount <= 3) {
            const nudgeDismissed = sessionStorage.getItem('tipNudgeDismissedToday');
            if (!nudgeDismissed) {
                // Show nudge after a delay
                setTimeout(() => {
                    this.showNudge();
                }, 3000);
            }
        }
    }

    showNudge() {
        const nudgeHTML = `
            <div class="tip-nudge-dialog">
                <div class="tip-nudge-content">
                    <h3>Ti stai godendo la musica di ${window.musicianName || 'questo musicista'}? 🎶</h3>
                    <p>Puoi lasciare una mancia se vuoi dirgli grazie.</p>
                </div>
                <div class="tip-nudge-actions">
                    <label class="tip-nudge-checkbox">
                        <input type="checkbox" id="nudgeDismissCheckbox">
                        <span>Non ricordarmelo più stasera</span>
                    </label>
                    <div class="tip-nudge-buttons">
                        <button class="tip-nudge-btn tip-nudge-btn-secondary" id="nudgeNotNow">Non ora</button>
                        <button class="tip-nudge-btn tip-nudge-btn-primary" id="nudgeLeaveTip">Lascia una mancia</button>
                    </div>
                </div>
            </div>
        `;

        const nudgeOverlay = document.createElement('div');
        nudgeOverlay.className = 'tip-nudge-overlay';
        nudgeOverlay.innerHTML = nudgeHTML;
        document.body.appendChild(nudgeOverlay);

        // Setup listeners
        document.getElementById('nudgeNotNow').addEventListener('click', () => {
            const dismissed = document.getElementById('nudgeDismissCheckbox').checked;
            if (dismissed) {
                sessionStorage.setItem('tipNudgeDismissedToday', 'true');
            }
            nudgeOverlay.remove();
        });

        document.getElementById('nudgeLeaveTip').addEventListener('click', () => {
            const dismissed = document.getElementById('nudgeDismissCheckbox').checked;
            if (dismissed) {
                sessionStorage.setItem('tipNudgeDismissedToday', 'true');
            }
            nudgeOverlay.remove();
            // Open standalone tip dialog
            this.showStandaloneTipDialog();
        });

        // Close on overlay click
        nudgeOverlay.addEventListener('click', (e) => {
            if (e.target === nudgeOverlay) {
                const dismissed = document.getElementById('nudgeDismissCheckbox').checked;
                if (dismissed) {
                    sessionStorage.setItem('tipNudgeDismissedToday', 'true');
                }
                nudgeOverlay.remove();
            }
        });
    }

    showStandaloneTipDialog() {
        // Similar to request dialog but without song selection
        const dialogHTML = `
            <div class="tip-dialog-header">
                <h2 class="tip-dialog-title">Supporta ${window.musicianName || 'il musicista'}</h2>
                <button class="tip-dialog-close" aria-label="Close">&times;</button>
            </div>
            <div class="tip-dialog-body">
                <div class="tip-dialog-message">
                    <p>Vuoi lasciare una mancia per <strong>${window.musicianName || 'il musicista'}</strong>?</p>
                </div>

                <div class="tip-dialog-tip-section">
                    <label class="tip-dialog-label">Importo mancia</label>
                    <div class="tip-amount-chips">
                        <button class="tip-chip" data-amount="2" data-label="Grazie">
                            2 €<br><small>Grazie</small>
                        </button>
                        <button class="tip-chip selected" data-amount="5" data-label="Offri un drink">
                            5 €<br><small>Offri un drink</small>
                        </button>
                        <button class="tip-chip" data-amount="10" data-label="Serata speciale">
                            10 €<br><small>Serata speciale</small>
                        </button>
                        <button class="tip-chip tip-chip-custom" data-amount="custom">
                            Altro
                        </button>
                    </div>
                    <div class="tip-custom-amount" id="tipCustomAmount" style="display: none;">
                        <input type="number" id="customTipInput" placeholder="Importo in €" min="1" step="0.50">
                    </div>
                </div>

                <div class="tip-dialog-payment-info">
                    <p>💳 Pagherai con PayPal al passo successivo.</p>
                </div>

                <div class="tip-dialog-actions">
                    <button class="tip-dialog-btn tip-dialog-btn-secondary" id="tipDialogCancel">Annulla</button>
                    <button class="tip-dialog-btn tip-dialog-btn-primary" id="tipDialogSubmit">
                        Invia mancia 5 €
                    </button>
                </div>
            </div>
        `;

        this.dialog.innerHTML = dialogHTML;
        this.selectedTipAmount = 5; // Default for standalone

        // Setup listeners (similar to request dialog)
        this.setupStandaloneTipListeners();
        this.show();
    }

    setupStandaloneTipListeners() {
        const closeBtn = this.dialog.querySelector('.tip-dialog-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.close());
        }

        const cancelBtn = this.dialog.querySelector('#tipDialogCancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.close());
        }

        const chips = this.dialog.querySelectorAll('.tip-chip');
        chips.forEach(chip => {
            chip.addEventListener('click', () => {
                chips.forEach(c => c.classList.remove('selected'));
                chip.classList.add('selected');
                
                const amount = chip.dataset.amount;
                if (amount === 'custom') {
                    document.getElementById('tipCustomAmount').style.display = 'block';
                    document.getElementById('customTipInput').focus();
                    this.selectedTipAmount = null;
                } else {
                    document.getElementById('tipCustomAmount').style.display = 'none';
                    this.selectedTipAmount = parseFloat(amount);
                    this.updateSubmitButton();
                }
            });
        });

        const customInput = document.getElementById('customTipInput');
        if (customInput) {
            customInput.addEventListener('input', (e) => {
                const value = parseFloat(e.target.value);
                if (value && value >= 1) {
                    this.selectedTipAmount = value;
                    this.updateSubmitButton();
                } else {
                    this.selectedTipAmount = null;
                    this.updateSubmitButton();
                }
            });
        }

        const submitBtn = this.dialog.querySelector('#tipDialogSubmit');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => this.submitStandaloneTip());
        }
    }

    async submitStandaloneTip() {
        const submitBtn = this.dialog.querySelector('#tipDialogSubmit');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Invio in corso...';
        }

        try {
            const response = await fetch('/api/create_tip', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tip_amount: this.selectedTipAmount
                })
            });

            const data = await response.json();

            if (data.success && data.tip_intent) {
                this.tipIntent = data.tip_intent;
                // Store PayPal client ID and mode from response
                if (data.paypal_client_id) {
                    this.tipIntent.paypal_client_id = data.paypal_client_id;
                }
                if (data.paypal_mode) {
                    this.tipIntent.paypal_mode = data.paypal_mode;
                }
                this.showSuccessMessage('Mancia creata!');
                setTimeout(() => {
                    this.showPaymentStep();
                }, 1500);
            } else {
                this.showError(data.error || 'Errore nella creazione mancia');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    this.updateSubmitButton();
                }
            }
        } catch (error) {
            console.error('Error creating tip:', error);
            this.showError('Errore: ' + error.message);
            if (submitBtn) {
                submitBtn.disabled = false;
                this.updateSubmitButton();
            }
        }
    }

    show() {
        if (this.overlay) {
            this.overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }

    close() {
        if (this.overlay) {
            this.overlay.classList.remove('active');
            document.body.style.overflow = '';
        }
        // Clear current state
        this.currentSong = null;
        this.currentUsername = null;
        this.selectedTipAmount = null;
        this.tipIntent = null;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize global instance
let tipDialog = null;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        tipDialog = new TipDialog();
        window.tipDialog = tipDialog;
    });
} else {
    tipDialog = new TipDialog();
    window.tipDialog = tipDialog;
}

