let html5QrCode = null;
let isAudioFeedbackEnabled = true;

// State Guard to prevent duplicate frame parsing during async shutdown
let isScanningActive = false;
let audioCtx = null;

function initAudioContext() {
    if (audioCtx) return;
    try {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    } catch (e) {
        console.warn("Web Audio API not supported:", e);
    }
}

function unlockAudioContext() {
    initAudioContext();
    if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume().then(() => {
            document.removeEventListener('click', unlockAudioContext);
            document.removeEventListener('touchstart', unlockAudioContext);
        });
    } else if (audioCtx) {
        document.removeEventListener('click', unlockAudioContext);
        document.removeEventListener('touchstart', unlockAudioContext);
    }
}

// Global gesture listeners to unlock browser AudioContext policies
document.addEventListener('click', unlockAudioContext);
document.addEventListener('touchstart', unlockAudioContext);

function playBeepSound() {
    if (!isAudioFeedbackEnabled) return;
    initAudioContext();
    if (!audioCtx || audioCtx.state === 'suspended') {
        console.warn("AudioContext suspended/blocked by browser autoplay policy.");
        return;
    }
    try {
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(1200, audioCtx.currentTime);
        gainNode.gain.setValueAtTime(0.3, audioCtx.currentTime);
        oscillator.start();
        oscillator.stop(audioCtx.currentTime + 0.08);
    } catch (e) {
        console.error("Failed to play scan beep:", e);
    }
}

document.addEventListener('alpine:init', () => {
    Alpine.data('scannerComponent', () => ({
        isOpen: false,
        targetTabId: '',
        statusMessage: '',
        currentFacingMode: 'environment',
        hasTorch: false,
        isTorchOn: false,

        init() {
            // Check global nav query trigger (?scan=true)
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('scan') === 'true') {
                setTimeout(() => {
                    const activeTabButton = document.querySelector('.tab-button.active');
                    if (activeTabButton) {
                        this.open(activeTabButton.dataset.tabId);
                    }
                }, 400);
            }
        },

        open(tabId) {
            this.isOpen = true;
            this.targetTabId = tabId;
            this.statusMessage = 'در حال اتصال به دوربین...';
            this.isTorchOn = false;
            isScanningActive = true;

            if (!html5QrCode) {
                html5QrCode = new Html5Qrcode("scanner-video-container");
            }

            const config = {
                fps: 15,
                qrbox: (width, height) => {
                    const size = Math.min(width, height) * 0.7;
                    return { width: size, height: size };
                },
                aspectRatio: 1.0
            };

            html5QrCode.start(
                { facingMode: this.currentFacingMode },
                config,
                (decodedText) => this.handleScanSuccess(decodedText),
                (errorMessage) => { /* Silent failure */ }
            ).then(() => {
                this.statusMessage = '';
                this.checkTorchAvailability();
            }).catch(err => {
                console.error("Camera access error:", err);
                this.statusMessage = 'خطا در اتصال به دوربین. لطفاً مجوز دسترسی را بررسی نمایید.';
            });
        },

        close() {
            this.isOpen = false;
            isScanningActive = false;
            this.isTorchOn = false;
            if (html5QrCode && html5QrCode.isScanning) {
                html5QrCode.stop().catch(err => {
                    console.error("Failed to stop scanner tracks:", err);
                });
            }
        },

        handleScanSuccess(decodedText) {
            if (!isScanningActive) return;
            isScanningActive = false;

            this.close();
            playBeepSound();
            if (navigator.vibrate) {
                navigator.vibrate(100);
            }

            // Populate matching check-in form and submit via HTMX
            const tabElement = document.getElementById(this.targetTabId);
            if (tabElement) {
                const input = tabElement.querySelector('input[name="id"]');
                if (input) {
                    input.value = decodedText;
                    const form = tabElement.querySelector('form');
                    if (form) {
                        // Submit using HTMX trigger
                        htmx.trigger(form, 'submit');
                    }
                }
            }
        },

        toggleCamera() {
            this.currentFacingMode = this.currentFacingMode === 'environment' ? 'user' : 'environment';
            if (html5QrCode && html5QrCode.isScanning) {
                html5QrCode.stop().then(() => {
                    this.open(this.targetTabId);
                });
            }
        },

        checkTorchAvailability() {
            if (html5QrCode && html5QrCode.isScanning) {
                try {
                    const capabilities = html5QrCode.getRunningTrackCameraCapabilities();
                    this.hasTorch = !!capabilities.torch;
                } catch (e) {
                    this.hasTorch = false;
                }
            }
        },

        toggleTorch() {
            if (html5QrCode && html5QrCode.isScanning && this.hasTorch) {
                this.isTorchOn = !this.isTorchOn;
                html5QrCode.applyVideoConstraints({
                    advanced: [{ torch: this.isTorchOn }]
                }).catch(err => {
                    console.error("Failed to apply torch constraint:", err);
                    this.isTorchOn = !this.isTorchOn; // rollback state
                });
            }
        }
    }));
});
