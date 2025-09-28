# ThermoScan - Industrial Temperature Monitoring Dashboard

A Flask-based web application for real-time temperature monitoring using AI vision models. The system captures images of temperature displays and uses AI models to extract numerical temperature readings.

## 🌟 Features

- **Real-time Camera Capture**: Capture temperature readings from industrial displays
- **Multiple AI Models**: Support for Gemini Pro Vision, Together AI, and Moondream
- **Temperature Monitoring**: Real-time temperature tracking with visual gauges
- **Data Export**: Export session data and full historical records
- **Webhook Integration**: Automatic alerts for critical temperatures
- **Responsive Design**: Works on desktop and mobile devices

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Webcam or camera device
- Modern web browser with camera access

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Pk-Kolhapurkar/Flask_temperature_dashboard.git
cd Flask_temperature_dashboard
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and navigate to `http://localhost:8001`

## 🔑 API Key Configuration

### Gemini Pro Vision
1. Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Open Settings in the app
3. Enter your Gemini API key

### Together AI
1. Get your API key from [Together AI](https://api.together.ai/)
2. Open Settings in the app  
3. Enter your Together AI API key

### Moondream (Free Tier Available!)
**No API key required!** The app includes built-in fallback handling:

- **Free Tier**: Leave the Moondream API key field blank to use the free tier
- **Automatic Fallback**: If the free API is unavailable, the app will simulate temperature readings
- **No Errors**: Users won't face errors even without an API key

## 🎯 How to Use

1. **Allow Camera Access**: Grant camera permissions when prompted
2. **Select AI Model**: Choose from Gemini, Together AI, or Moondream
3. **Capture & Analyze**: Click "Capture & Analyze" to process the image
4. **View Results**: See temperature readings, status, and historical data
5. **Configure Settings**: Set warning/critical thresholds and API keys

## ⚙️ Settings

### Temperature Thresholds
- **Warning Threshold**: Default 30°C (configurable)
- **Critical Threshold**: Default 35°C (configurable)

### API Keys
- Store API keys securely in browser localStorage
- Keys persist between sessions
- Moondream works without any API key configuration

## 📊 Data Management

### Local Storage
- Temperature readings stored in SQLite database (`session.db`)
- Session data persists until reset

### MongoDB Integration (Optional)
- Configure MongoDB Atlas connection in `.env`
- Full historical data storage
- Export functionality for complete datasets

## 🛠️ Technical Details

### Backend
- **Framework**: Flask
- **Database**: SQLite + MongoDB (optional)
- **AI Models**: Gemini Pro Vision, Together AI, Moondream
- **Image Processing**: Base64 encoding, PIL for image handling

### Frontend
- **Framework**: Vanilla JavaScript + HTML5 + CSS3
- **Charts**: Chart.js for live temperature graphs
- **UI**: Industrial-themed responsive design
- **Camera**: WebRTC for camera access

## 🔧 Troubleshooting

### Common Issues

**Camera Not Working:**
- Check browser permissions
- Ensure camera is not being used by another application

**API Key Errors:**
- Gemini/Together AI: Ensure valid API keys are entered
- Moondream: No API key needed - uses free tier with fallback

**Processing Errors:**
- The app includes robust error handling
- Moondream will automatically use simulated temperatures if API fails

### Debug Mode
- Check the System Console for real-time debug information
- All API calls and errors are logged

## 📈 Webhook Integration

The app can send alerts to external services when critical temperatures are detected:

```javascript
// Webhook payload example
{
  "temperature": 38.5,
  "timestamp": "2024-01-15T10:30:00Z",
  "status": "critical",
  "message": "⚠️ Critical temperature detected",
  "deviceInfo": "Mozilla/5.0..."
}
```

## 🚀 Deployment

### Local Deployment
```bash
python app.py
```

### Production Deployment
1. Set environment variables:
```bash
export PORT=8000
export MONGODB_URI=your_mongodb_uri
```

2. Use production WSGI server:
```bash
gunicorn app:app -b 0.0.0.0:8000
```

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "app.py"]
```

## 📝 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For issues and questions:
1. Check the System Console for debug information
2. Review the troubleshooting section
3. Open an issue on GitHub

---

**Note**: Moondream API is designed to work without configuration - simply leave the API key field blank to use the free tier with automatic fallback handling!
