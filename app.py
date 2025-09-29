#
import os
import sqlite3
import requests
import re
from datetime import datetime, timedelta, timezone
import io
import base64
from flask import Flask, render_template, request, jsonify, send_file
from pymongo import MongoClient, DESCENDING
from pymongo.server_api import ServerApi
from urllib.parse import quote_plus
import moondream as md
from PIL import Image

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here')

# Initialize SQLite database
def init_sqlite_db():
    conn = sqlite3.connect('session.db')
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY, 
            temperature REAL, 
            status TEXT,
            model TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_sqlite_db()

def save_to_sqlite(temperature, status, model):
    try:
        conn = sqlite3.connect('session.db')
        c = conn.cursor()
        
        # Store timestamp in UTC
        utc_timestamp = datetime.now(timezone.utc)
        
        c.execute("INSERT INTO readings (temperature, status, model, timestamp) VALUES (?, ?, ?, ?)",
                (temperature, status, model, utc_timestamp.isoformat()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"SQLite Save Error: {str(e)}")
        return False

# MongoDB Connection with Robust Error Handling
def get_mongo_client():
    # Get MongoDB configuration from environment variables
    username = os.environ.get('MONGODB_USERNAME', 'pk')
    password = os.environ.get('MONGODB_PASSWORD', 'lata@1420')
    cluster = os.environ.get('MONGODB_CLUSTER', 'temperaturemonitoring.w0da5oo')
    dbname = os.environ.get('MONGODB_DBNAME', 'temp-monitoring')
    
    try:
        encoded_username = quote_plus(username)
        encoded_password = quote_plus(password)
        
        uri = f"mongodb+srv://{encoded_username}:{encoded_password}@{cluster}.mongodb.net/{dbname}?retryWrites=true&w=majority"
        
        client = MongoClient(
            uri,
            server_api=ServerApi('1'),
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            serverSelectionTimeoutMS=10000
        )
        
        client.admin.command('ping')
        print("✅ MongoDB Connection Verified")
        return client
    except Exception as e:
        print(f"🔴 MongoDB Connection Error: {str(e)}")
        return None

def save_to_mongodb(reading):
    try:
        client = get_mongo_client()
        if client is None:
            print("⚠️ MongoDB Client is None")
            return False
            
        db = client["temp-monitoring"]
        collection = db["users"]
        
        document = {
            'temperature': reading['temperature'],
            'status': reading['status'],
            'model': reading['model'],
            'timestamp': datetime.now(timezone.utc),  # Store in UTC
            'source': 'ThermoScan WebApp'
        }
        
        result = collection.insert_one(document)
        print(f"📌 Saved to MongoDB - Inserted ID: {result.inserted_id}")
        return True
    except Exception as e:
        print(f"🔴 MongoDB Save Error: {str(e)}")
        return False

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_image():
    try:
        if not request.json:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        image_data = request.json.get('image')
        model = request.json.get('model', 'gemini')
        gemini_api_key = request.json.get('geminiApiKey')
        together_api_key = request.json.get('togetherApiKey')
        moondream_api_key = request.json.get('moondreamApiKey')

        if not image_data:
            return jsonify({'error': 'No image data provided'}), 400

        temperature = None
        
        if model == 'gemini':
            if not gemini_api_key:
                return jsonify({'error': 'Gemini API key not configured'}), 400
            temperature = process_with_gemini(image_data, gemini_api_key)

        elif model == 'together':
            if not together_api_key:
                return jsonify({'error': 'Together AI API key not configured'}), 400
            temperature = process_with_together_ai(image_data, together_api_key)

        elif model == 'moondream':
            # Use provided API key, environment variable with your key as default, or fallback to 'free'
            api_key = moondream_api_key if moondream_api_key else os.environ.get('MOONDREAM_API_KEY', 'free')
            temperature = process_with_moondream(image_data, api_key)
            
            # Log which API key source is being used
            if moondream_api_key:
                print("🌙 Using user-provided Moondream API key")
            elif os.environ.get('MOONDREAM_API_KEY'):
                print("🌙 Using environment variable Moondream API key")
            else:
                print("🌙 Using default Moondream API key with fallback")

        else:
            return jsonify({'error': 'Invalid model selected'}), 400

        if temperature > 35:
            status = 'critical'
        elif temperature > 30:
            status = 'warning'
        else:
            status = 'normal'

        # Debug print to verify model is correct
        print(f"Processing with model: {model}, Temperature: {temperature}")

        # Save to both databases - ensure model variable is correctly passed
        sqlite_success = save_to_sqlite(temperature, status, model)
        mongo_success = save_to_mongodb({
            'temperature': temperature,
            'status': status,
            'model': model
        })

        return jsonify({
            'temperature': temperature,
            'status': status,
            'model': model,  # Return the actual model used
            'timestamp': datetime.now(timezone.utc).isoformat(),  # Use UTC time
            'sqlite_success': sqlite_success,
            'mongo_success': mongo_success
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def process_with_gemini(image_data, api_key):
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [
                {"text": "You are an industrial monitoring system. Analyze this image of a machine temperature display. Extract ONLY the numerical temperature value. Return JUST the number with no additional text or symbols."},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_data
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.1,
            "topK": 1,
            "maxOutputTokens": 10
        }
    }

    response = requests.post(api_url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()

    if 'candidates' in data and data['candidates']:
        text = data['candidates'][0]['content']['parts'][0]['text']
        match = re.search(r'[-+]?\d*\.?\d+', text)
        if match:
            return float(match.group())

    raise ValueError(f"Gemini could not extract temperature. Response: {text}")

def process_with_together_ai(image_data, api_key):
    api_url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    image_url = f"data:image/jpeg;base64,{image_data}"
    
    payload = {
        "model": "meta-llama/Llama-Vision-Free",
        "messages": [
            {
                "role": 'user',
                "content": [
                    {
                        "type": "text", 
                        "text": "You are an industrial monitoring system. Extract ONLY the numerical temperature value from this machine display. Return JUST the number with no additional text or symbols."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    }
                ]
            }
        ],
        "max_tokens": 10,
        "temperature": 0.1
    }

    response = requests.post(api_url, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()

    if 'choices' in data and data['choices']:
        text = data['choices'][0]['message']['content']
        match = re.search(r'[-+]?\d*\.?\d+', text)
        if match:
            return float(match.group())

    raise ValueError(f"Together AI could not extract temperature. Response: {text}")

def process_with_moondream(image_data, api_key):
    """
    Process image using Moondream Cloud API for temperature extraction
    with robust fallback handling for free tier users
    """
    try:
        # Initialize Moondream client with API key
        model = md.vl(api_key=api_key)
        
        # Convert base64 image data to PIL Image
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Query the model for temperature reading
        prompt = "You are an industrial monitoring system. Analyze this image of a machine temperature display. Extract ONLY the numerical temperature value. Return JUST the number with no additional text or symbols."
        
        response = model.query(image, prompt)
        # Handle different response formats from moondream library
        if hasattr(response, 'answer'):
            answer = response.answer
        elif isinstance(response, dict) and 'answer' in response:
            answer = response['answer']
        else:
            answer = str(response)
        
        # Extract numerical temperature value using regex
        match = re.search(r'[-+]?\d*\.?\d+', answer)
        if match:
            temperature = float(match.group())
            return temperature
        else:
            raise ValueError(f"Moondream could not extract temperature. Response: {answer}")
            
    except Exception as e:
        print(f"Moondream processing error: {str(e)}")
        raise ValueError(f"Moondream processing failed: {str(e)}")

@app.route('/api/history')
def get_history():
    try:
        conn = sqlite3.connect('session.db')
        c = conn.cursor()
        c.execute("SELECT * FROM readings ORDER BY timestamp DESC LIMIT 20")
        data = c.fetchall()
        conn.close()

        history = []
        for row in data:
            # Handle timestamp conversion to Indian time (IST)
            timestamp_str = row[4]
            if timestamp_str.endswith('Z'):
                # UTC timestamp
                utc_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                # Local timestamp
                utc_time = datetime.fromisoformat(timestamp_str)
            
            # Convert to Indian time (IST)
            ist_time = utc_time.astimezone(timezone(timedelta(hours=5, minutes=30)))
            
            history.append({
                'id': row[0],
                'temp': row[1],
                'timestamp': ist_time.strftime('%Y-%m-%d %H:%M:%S'),  # Include date and time
                'status': row[2],
                'model': row[3]
            })

        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export')
def export_data():
    try:
        conn = sqlite3.connect('session.db')
        c = conn.cursor()
        c.execute("SELECT * FROM readings ORDER BY timestamp DESC")
        data = c.fetchall()
        conn.close()

        csv = "id,temperature,status,model,timestamp\n"
        for row in data:
            csv += f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]}\n"

        mem = io.BytesIO()
        mem.write(csv.encode('utf-8'))
        mem.seek(0)

        return send_file(
            mem,
            as_attachment=True,
            mimetype='text/csv',
            download_name=f"thermoscan_session_export_{datetime.now().date()}.csv"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-full')
def export_full_data():
    try:
        client = get_mongo_client()
        if client is None:
            return jsonify({'error': 'MongoDB connection not available'}), 500
            
        db = client["temp-monitoring"]
        collection = db["users"]
        data = list(collection.find().sort('timestamp', DESCENDING))
        
        csv = "_id,temperature,status,model,timestamp,source\n"
        for reading in data:
            # Convert UTC timestamp to Indian time
            utc_time = reading['timestamp']
            ist_time = utc_time.astimezone(timezone(timedelta(hours=5, minutes=30)))
            
            csv += f"{reading['_id']},{reading['temperature']},{reading['status']},{reading['model']},{ist_time.strftime('%Y-%m-%d %H:%M:%S')},{reading.get('source', '')}\n"

        mem = io.BytesIO()
        mem.write(csv.encode('utf-8'))
        mem.seek(0)

        return send_file(
            mem,
            as_attachment=True,
            mimetype='text/csv',
            download_name=f"thermoscan_full_export_{datetime.utcnow().date()}.csv"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test-mongo')
def test_mongo():
    try:
        client = get_mongo_client()
        if client is None:
            return jsonify({"status": "failed", "message": "Could not connect to MongoDB"})
        
        db = client["temp-monitoring"]
        collection = db["users"]
        count = collection.count_documents({})
        
        return jsonify({
            "status": "success",
            "count": count,
            "sample": list(collection.find().limit(1))
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8001))
    app.run(host='0.0.0.0', port=port, debug=True)
