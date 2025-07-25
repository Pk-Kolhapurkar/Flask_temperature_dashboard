// DOM Elements
const cameraFeed = document.getElementById('cameraFeed');
const captureCanvas = document.getElementById('captureCanvas');
const currentTempEl = document.getElementById('currentTemp');
const maxTempEl = document.getElementById('maxTemp');
const minTempEl = document.getElementById('minTemp');
const tempStatusEl = document.getElementById('tempStatus');
const historyBody = document.getElementById('historyBody');
const gaugeProgress = document.getElementById('gaugeProgress');
const gaugeValue = document.getElementById('gaugeValue');
const lastOcrResult = document.getElementById('lastOcrResult');
const modelSelector = document.getElementById('modelSelector');
const currentModelDisplay = document.getElementById('currentModelDisplay');
const activeModelStatus = document.getElementById('activeModelStatus');
const processingOverlay = document.getElementById('processingOverlay');
const processingModel = document.getElementById('processingModel');
const apiStatus = document.getElementById('apiStatus');

// App State
let temperatureHistory = [];
let maxTemp = null;
let minTemp = null;
let stream = null;
let currentModel = 'gemini';
let liveChart = null;
let chartData = {
    labels: [],
    datasets: [{
        label: 'Temperature (°C)',
        data: [],
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56, 189, 248, 0.1)',
        borderWidth: 2,
        pointRadius: 3,
        tension: 0.1,
        fill: true
    }]
};

// Initialize the app
async function init() {
    // Initialize camera when user clicks capture for the first time
    document.getElementById('captureBtn').addEventListener('click', initCamera);
    
    // Set up model selector
    modelSelector.addEventListener('change', function() {
        currentModel = this.value;
        const modelName = this.options[this.selectedIndex].text;
        currentModelDisplay.textContent = modelName;
        activeModelStatus.textContent = modelName;
    });
    
    // Set up capture button
    document.getElementById('captureBtn').addEventListener('click', captureAndProcess);
    
    // Initialize gauge
    updateGauge(0);
    
    // Settings modal
    document.getElementById('settingsBtn').addEventListener('click', () => {
        document.getElementById('settingsModal').classList.remove('hidden');
    });
    
    document.getElementById('closeSettingsModal').addEventListener('click', () => {
        document.getElementById('settingsModal').classList.add('hidden');
    });
    
    document.getElementById('cancelSettings').addEventListener('click', () => {
        document.getElementById('settingsModal').classList.add('hidden');
    });
    
    document.getElementById('saveSettings').addEventListener('click', saveSettings);
    
    // Initialize chart
    initLiveChart();
    
    // Export data button
    document.getElementById('exportDataBtn').addEventListener('click', exportData);
    
    // Load history from backend
    await loadHistory();
}

async function initCamera() {
    try {
        if (!stream) {
            stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    facingMode: 'environment',
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                } 
            });
            cameraFeed.srcObject = stream;
        }
    } catch (err) {
        console.error("Error accessing camera:", err);
        cameraFeed.parentElement.innerHTML = `
            <div class="text-center text-industrial-300 p-4">
                <i class="fas fa-video-slash text-4xl mb-2"></i>
                <p>Could not access camera. Please check permissions.</p>
                <button onclick="window.location.reload()" class="mt-2 bg-industrial-600 hover:bg-industrial-500 text-white px-4 py-2 rounded-lg">
                    Try Again
                </button>
            </div>
        `;
    }
    // Remove this event listener after first run
    document.getElementById('captureBtn').removeEventListener('click', initCamera);
}

async function captureAndProcess() {
    if (!stream) return;
    
    // Show processing overlay
    processingOverlay.classList.remove('hidden');
    processingModel.textContent = currentModel === 'gemini' ? 'Gemini' : 'Qwen';
    
    try {
        // Capture frame
        const context = captureCanvas.getContext('2d');
        captureCanvas.width = cameraFeed.videoWidth;
        captureCanvas.height = cameraFeed.videoHeight;
        context.drawImage(cameraFeed, 0, 0, captureCanvas.width, captureCanvas.height);
        
        // Convert to base64 for API
        const imageData = captureCanvas.toDataURL('image/jpeg').split(',')[1];
        
        // Send to backend for processing
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                image: imageData,
                model: currentModel
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Update UI with results
        updateTemperature(data.temperature, data.model);
        lastOcrResult.textContent = `${data.model} detected temperature: ${data.temperature}°C`;
        
    } catch (error) {
        console.error("Processing error:", error);
        lastOcrResult.textContent = `Error: ${error.message}`;
    } finally {
        processingOverlay.classList.add('hidden');
    }
}

async function loadHistory() {
    try {
        const response = await fetch('/api/history');
        const history = await response.json();
        temperatureHistory = history;
        updateHistoryTable();
        
        // Update min/max temps
        if (history.length > 0) {
            const temps = history.map(item => item.temp);
            maxTemp = Math.max(...temps);
            minTemp = Math.min(...temps);
            maxTempEl.textContent = `${maxTemp}°C`;
            minTempEl.textContent = `${minTemp}°C`;
            
            // Update chart
            history.forEach(reading => {
                updateLiveChart(reading.temp, reading.timestamp);
            });
        }
    } catch (error) {
        console.error("Error loading history:", error);
    }
}

// ... [Include all other JavaScript functions from the original file] ...
// ... [updateTemperature, updateGauge, updateHistoryTable, etc.] ...

document.addEventListener('DOMContentLoaded', init);