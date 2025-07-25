// static/js/main.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the application
    initApp();
});

function initApp() {
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
    const debugConsole = document.getElementById('debugConsole');
    
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
        // Set up model selector
        modelSelector.addEventListener('change', function() {
            currentModel = this.value;
            const modelName = this.options[this.selectedIndex].text;
            currentModelDisplay.textContent = modelName;
            activeModelStatus.textContent = modelName;
            logDebug(`Switched to ${modelName} model`);
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
        
        // Start/stop periodic capture
        let captureInterval;
        const captureBtn = document.getElementById('captureBtn');
        const stopRecordingBtn = document.getElementById('stopRecordingBtn');
        
        captureBtn.addEventListener('click', () => {
            if (captureInterval) {
                stopPeriodicCapture(captureInterval);
                captureInterval = null;
                captureBtn.innerHTML = '<i class="fas fa-camera mr-1"></i> Capture & Analyze';
                stopRecordingBtn.classList.add('hidden');
            } else {
                captureInterval = startPeriodicCapture(10);
                captureBtn.innerHTML = '<i class="fas fa-pause mr-1"></i> Pause Recording';
                stopRecordingBtn.classList.remove('hidden');
            }
        });

        stopRecordingBtn.addEventListener('click', () => {
            if (captureInterval) {
                stopPeriodicCapture(captureInterval);
                captureInterval = null;
                captureBtn.innerHTML = '<i class="fas fa-camera mr-1"></i> Capture & Analyze';
                stopRecordingBtn.classList.add('hidden');
            }
        });
        
        // Load initial history
        await loadHistory();
    }

    // Initialize camera
    async function initCamera() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    facingMode: 'environment',
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                } 
            });
            cameraFeed.srcObject = stream;
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
    }

    // Capture and process image
    async function captureAndProcess() {
        try {
            // Initialize camera if not already done
            if (!stream) {
                await initCamera();
            }
            
            // Show processing overlay
            processingOverlay.classList.remove('hidden');
            processingModel.textContent = currentModel === 'gemini' ? 'Gemini' : 'Qwen';
            
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
            logDebug(`Processing error: ${error.message}`);
        } finally {
            processingOverlay.classList.add('hidden');
        }
    }

    // Load temperature history
    async function loadHistory() {
        try {
            const response = await fetch('/api/history');
            const history = await response.json();
            temperatureHistory = history;
            
            if (history.length > 0) {
                // Update min/max temperatures
                const temps = history.map(item => item.temp);
                maxTemp = Math.max(...temps);
                minTemp = Math.min(...temps);
                maxTempEl.textContent = `${maxTemp}°C`;
                minTempEl.textContent = `${minTemp}°C`;
                
                // Update chart with all history
                history.forEach(reading => {
                    updateLiveChart(reading.temp, reading.timestamp);
                });
                
                // Update history table
                updateHistoryTable();
            }
        } catch (error) {
            console.error("Error loading history:", error);
            logDebug(`History load error: ${error.message}`);
        }
    }

    // Update temperature display
    function updateTemperature(temp, model) {
        currentTempEl.textContent = `${temp}°C`;
        updateGauge(temp);
        updateStatus(temp);
    
        const timestamp = new Date().toLocaleTimeString();
        const status = getStatus(temp);
        
        // Add to local history
        temperatureHistory.unshift({
            temp: temp,
            timestamp: timestamp,
            status: status,
            model: model
        });
    
        // Keep only last 20 readings
        if (temperatureHistory.length > 20) {
            temperatureHistory.pop();
        }
    
        // Update min/max temps
        if (maxTemp === null || temp > maxTemp) {
            maxTemp = temp;
            maxTempEl.textContent = `${maxTemp}°C`;
        }
    
        if (minTemp === null || temp < minTemp) {
            minTemp = temp;
            minTempEl.textContent = `${minTemp}°C`;
        }
    
        updateHistoryTable();
        updateLiveChart(temp, timestamp);
        
        // Check for critical temperature
        checkCriticalTemperature(temp);
    }

    // Update gauge display
    function updateGauge(temp) {
        // Normalize temperature to gauge range (0-50°C)
        const percentage = Math.min(Math.max((temp / 50) * 100, 0), 100);
        const dashValue = (565 * percentage) / 100;
        
        gaugeProgress.style.strokeDasharray = `${dashValue} 565`;
        gaugeValue.textContent = `${temp}°C`;
        
        // Update gauge color based on temperature
        if (temp > criticalThreshold) {
            gaugeProgress.style.stroke = '#ef4444';
        } else if (temp > warningThreshold) {
            gaugeProgress.style.stroke = '#f59e0b';
        } else {
            gaugeProgress.style.stroke = '#38bdf8';
        }
    }

    // Update temperature status
    function updateStatus(temp) {
        const statusIndicator = tempStatusEl.querySelector('.status-indicator');
        statusIndicator.className = 'status-indicator';
        
        if (temp > criticalThreshold) {
            tempStatusEl.innerHTML = '<span class="status-indicator status-danger"></span> CRITICAL TEMPERATURE';
            tempStatusEl.className = 'mt-2 px-3 py-1 rounded-full bg-danger-900 text-danger-200 text-sm';
            currentTempEl.classList.add('text-danger-500');
            currentTempEl.classList.remove('text-industrial-200', 'text-warning-500');
        } else if (temp > warningThreshold) {
            tempStatusEl.innerHTML = '<span class="status-indicator status-warning"></span> HIGH TEMPERATURE';
            tempStatusEl.className = 'mt-2 px-3 py-1 rounded-full bg-warning-900 text-warning-200 text-sm';
            currentTempEl.classList.add('text-warning-500');
            currentTempEl.classList.remove('text-industrial-200', 'text-danger-500');
        } else {
            tempStatusEl.innerHTML = '<span class="status-indicator status-normal"></span> NORMAL';
            tempStatusEl.className = 'mt-2 px-3 py-1 rounded-full bg-industrial-800 text-industrial-300 text-sm';
            currentTempEl.classList.add('text-industrial-200');
            currentTempEl.classList.remove('text-warning-500', 'text-danger-500');
        }
    }

    // Update history table
    function updateHistoryTable() {
        if (temperatureHistory.length === 0) {
            historyBody.innerHTML = `
                <tr>
                    <td colspan="5" class="px-4 py-8 text-center text-industrial-500">
                        No temperature data recorded yet
                    </td>
                </tr>
            `;
            return;
        }
        
        let historyHTML = '';
        temperatureHistory.forEach(reading => {
            let statusClass = '';
            let statusText = '';
            
            switch(reading.status) {
                case 'critical':
                    statusClass = 'text-danger-500';
                    statusText = 'Critical';
                    break;
                case 'warning':
                    statusClass = 'text-warning-500';
                    statusText = 'Warning';
                    break;
                default:
                    statusClass = 'text-success-500';
                    statusText = 'Normal';
            }
            
            historyHTML += `
                <tr class="history-item">
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-industrial-300">${reading.timestamp}</td>
                    <td class="px-4 py-3 whitespace-nowrap">
                        <div class="text-lg font-bold ${reading.status === 'critical' ? 'text-danger-500' : reading.status === 'warning' ? 'text-warning-500' : 'text-industrial-200'}">
                            ${reading.temp}°C
                        </div>
                    </td>
                    <td class="px-4 py-3 whitespace-nowrap">
                        <span class="${statusClass} font-medium">${statusText}</span>
                    </td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-industrial-400">
                        ${reading.model}
                    </td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm">
                        <button class="text-industrial-400 hover:text-industrial-300 mr-2">
                            <i class="fas fa-chart-line"></i>
                        </button>
                        <button class="text-industrial-400 hover:text-industrial-300">
                            <i class="fas fa-info-circle"></i>
                        </button>
                    </td>
                </tr>
            `;
        });
        
        historyBody.innerHTML = historyHTML;
    }

    // Export data
    async function exportData() {
        try {
            const response = await fetch('/api/export');
            const blob = await response.blob();
            
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `thermoscan_export_${new Date().toISOString().slice(0,10)}.csv`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            logDebug("Data exported successfully");
        } catch (error) {
            console.error("Export error:", error);
            logDebug(`Export error: ${error.message}`);
        }
    }

    // Initialize live chart
    function initLiveChart() {
        const ctx = document.getElementById('liveChart').getContext('2d');
        liveChart = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 1000,
                    easing: 'linear'
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        grid: {
                            color: 'rgba(30, 41, 59, 0.5)'
                        },
                        ticks: {
                            color: '#94a3b8'
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(30, 41, 59, 0.5)'
                        },
                        ticks: {
                            color: '#94a3b8',
                            maxRotation: 45,
                            minRotation: 45
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: '#e2e8f0'
                        }
                    },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        titleColor: '#e2e8f0',
                        bodyColor: '#e2e8f0',
                        borderColor: '#334155',
                        borderWidth: 1
                    }
                }
            }
        });
    }

    // Update live chart
    function updateLiveChart(temp, timestamp) {
        chartData.labels.push(timestamp);
        chartData.datasets[0].data.push(temp);
        
        // Keep only last 20 points
        if (chartData.labels.length > 20) {
            chartData.labels.shift();
            chartData.datasets[0].data.shift();
        }
        
        liveChart.update();
    }

    // Debug logging
    function logDebug(message) {
        if (!debugConsole) return;
        
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.innerHTML = `[${timestamp}] ${message}`;
        debugConsole.appendChild(logEntry);
        debugConsole.scrollTop = debugConsole.scrollHeight;
        
        // Keep only last 100 messages
        if (debugConsole.children.length > 100) {
            debugConsole.removeChild(debugConsole.children[0]);
        }
    }

    // Get temperature status
    function getStatus(temp) {
        const warningThreshold = 30;
        const criticalThreshold = 35;
        
        if (temp > criticalThreshold) return 'critical';
        if (temp > warningThreshold) return 'warning';
        return 'normal';
    }

    // Check critical temperature
    function checkCriticalTemperature(temp) {
        const criticalThreshold = 35;
        if (temp > criticalThreshold) {
            logDebug(`Critical temperature detected: ${temp}°C`);
        }
    }

    // Save settings
    function saveSettings() {
        // This is now frontend-only since API keys aren't used in backend simulation
        const geminiApiKey = document.getElementById('geminiApiKey').value.trim();
        const huggingfaceApiKey = document.getElementById('huggingfaceApiKey').value.trim();
        const warningThreshold = parseInt(document.getElementById('warningThreshold').value) || 30;
        const criticalThreshold = parseInt(document.getElementById('criticalThreshold').value) || 35;
        
        localStorage.setItem('geminiApiKey', geminiApiKey);
        localStorage.setItem('huggingfaceApiKey', huggingfaceApiKey);
        localStorage.setItem('warningThreshold', warningThreshold);
        localStorage.setItem('criticalThreshold', criticalThreshold);
        
        document.getElementById('settingsModal').classList.add('hidden');
        logDebug("Settings saved to local storage");
    }

    // Start periodic capture
    function startPeriodicCapture(intervalSeconds = 10) {
        logDebug(`Starting periodic capture every ${intervalSeconds} seconds`);
        captureAndProcess(); // Capture immediately
        return setInterval(captureAndProcess, intervalSeconds * 1000);
    }

    // Stop periodic capture
    function stopPeriodicCapture(intervalId) {
        clearInterval(intervalId);
        logDebug("Stopped periodic capture");
    }

    // Initialize the app
    init();
}