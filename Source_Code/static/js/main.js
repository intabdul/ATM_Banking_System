// ATM System JavaScript

document.addEventListener('DOMContentLoaded', function() {
    
    // Session timeout warning
    let sessionTimeout = 10 * 60; // 10 minutes in seconds
    let warningTime = 60; // Show warning 1 minute before timeout
    
    function checkSession() {
        if (sessionTimeout > 0) {
            sessionTimeout--;
            
            if (sessionTimeout === warningTime) {
                showSessionWarning();
            }
            
            if (sessionTimeout <= 0) {
                window.location.href = '/logout/';
            }
        }
    }
    
    // Check session every second
    setInterval(checkSession, 1000);
    
    function showSessionWarning() {
        if (document.getElementById('session-warning')) return;
        
        const warning = document.createElement('div');
        warning.id = 'session-warning';
        warning.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #f39c12;
            color: white;
            padding: 15px;
            border-radius: 5px;
            z-index: 1000;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            animation: slideIn 0.3s ease;
        `;
        
        warning.innerHTML = `
            <strong><i class="fas fa-clock"></i> Session Expiring Soon</strong>
            <p>Your session will expire in 1 minute. Please save your work.</p>
            <button onclick="extendSession()" style="background: white; color: #f39c12; border: none; padding: 5px 10px; border-radius: 3px; margin-top: 5px; cursor: pointer;">
                Extend Session
            </button>
        `;
        
        document.body.appendChild(warning);
        
        // Auto remove after 10 seconds
        setTimeout(() => {
            if (warning.parentNode) {
                warning.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => warning.remove(), 300);
            }
        }, 10000);
    }
    
    window.extendSession = function() {
        fetch('/dashboard/', {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        }).then(() => {
            const warning = document.getElementById('session-warning');
            if (warning) {
                warning.style.background = '#27ae60';
                warning.innerHTML = '<strong><i class="fas fa-check"></i> Session Extended</strong><p>Your session has been extended.</p>';
                setTimeout(() => warning.remove(), 3000);
            }
            sessionTimeout = 10 * 60; // Reset to 10 minutes
        });
    };
    
    // Amount input formatting
    const amountInputs = document.querySelectorAll('input[name="amount"]');
    amountInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            let value = e.target.value.replace(/[^\d.]/g, '');
            
            // Ensure only two decimal places
            if (value.includes('.')) {
                const parts = value.split('.');
                if (parts[1].length > 2) {
                    parts[1] = parts[1].substring(0, 2);
                }
                value = parts[0] + '.' + parts[1];
            }
            
            e.target.value = value;
        });
        
        // Add thousand separators on blur
        input.addEventListener('blur', function(e) {
            let value = e.target.value;
            if (value && !isNaN(parseFloat(value))) {
                const num = parseFloat(value);
                e.target.value = num.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            }
        });
    });
    
    // PIN input masking
    const pinInputs = document.querySelectorAll('input[type="password"][maxlength="4"]');
    pinInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            // Only allow numbers
            e.target.value = e.target.value.replace(/\D/g, '');
            
            // Auto-tab to next PIN digit (if implementing 4 separate fields)
            if (e.target.value.length === e.target.maxLength) {
                const next = e.target.nextElementSibling;
                if (next && next.tagName === 'INPUT') {
                    next.focus();
                }
            }
        });
    });
    
    // Quick withdrawal buttons
    document.querySelectorAll('.quick-withdraw').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const amount = this.getAttribute('data-amount');
            const amountInput = document.querySelector('input[name="amount"]');
            if (amountInput) {
                amountInput.value = amount;
                amountInput.focus();
            }
        });
    });
    
    // Print receipt confirmation
    const printButtons = document.querySelectorAll('a[href*="print-receipt"]');
    printButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Do you want to print the receipt? Make sure your printer is ready.')) {
                e.preventDefault();
            }
        });
    });
    
    // Form validation enhancement
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                
                // Re-enable after 5 seconds in case of error
                setTimeout(() => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = submitBtn.getAttribute('data-original-text') || 'Submit';
                }, 5000);
            }
        });
    });
    
    // Add CSS for animations
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
        
        .fa-spin {
            animation: fa-spin 1s linear infinite;
        }
        
        @keyframes fa-spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);
    
    // ATM sound effects (optional)
    window.playATMSound = function(soundType) {
        const sounds = {
            'button': 'https://assets.mixkit.co/sfx/preview/mixkit-select-click-1109.mp3',
            'success': 'https://assets.mixkit.co/sfx/preview/mixkit-correct-answer-tone-2870.mp3',
            'error': 'https://assets.mixkit.co/sfx/preview/mixkit-wrong-answer-fail-notification-946.mp3'
        };
        
        if (sounds[soundType]) {
            const audio = new Audio(sounds[soundType]);
            audio.volume = 0.3;
            audio.play().catch(() => {
                // Sound play failed, ignore
            });
        }
    };
    
    // Add click sounds to buttons
    document.querySelectorAll('button, .atm-btn, a[href]').forEach(btn => {
        if (!btn.href || !btn.href.includes('logout')) {
            btn.addEventListener('click', () => {
                playATMSound('button');
            });
        }
    });
});