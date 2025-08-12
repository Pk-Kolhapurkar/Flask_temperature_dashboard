'''import os
import sqlite3
import requests
import re
from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Database setup
def init_db():
    conn = sqlite3.connect('temperature.db')
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

init_db()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_image():
    try:
        image_data = request.json.get('image')
        model = request.json.get('model', 'gemini')
        gemini_api_key = request.json.get('geminiApiKey')
        together_api_key = request.json.get('togetherApiKey')  # Changed from huggingfaceApiKey

        if not image_data:
            return jsonify({'error': 'No image data provided'}), 400

        if model == 'gemini':
            if not gemini_api_key:
                return jsonify({'error': 'Gemini API key not configured'}), 400
            temperature = process_with_gemini(image_data, gemini_api_key)

        elif model == 'together':  # Changed from 'qwen'
            if not together_api_key:
                return jsonify({'error': 'Together AI API key not configured'}), 400
            temperature = process_with_together_ai(image_data, together_api_key)

        else:
            return jsonify({'error': 'Invalid model selected'}), 400

        if temperature > 35:
            status = 'critical'
        elif temperature > 30:
            status = 'warning'
        else:
            status = 'normal'

        conn = sqlite3.connect('temperature.db')
        c = conn.cursor()
        c.execute("INSERT INTO readings (temperature, status, model) VALUES (?, ?, ?)",
                  (temperature, status, model))
        conn.commit()
        conn.close()

        return jsonify({
            'temperature': temperature,
            'status': status,
            'model': model.capitalize()
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
    
    # Create the data URL for the image
    image_url = f"data:image/jpeg;base64,{image_data}"
    
    payload = {
        "model": "meta-llama/Llama-Vision-Free",
        "messages": [
            {
                "role": "user",
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

@app.route('/api/history')
def get_history():
    conn = sqlite3.connect('temperature.db')
    c = conn.cursor()
    c.execute("SELECT * FROM readings ORDER BY timestamp DESC LIMIT 20")
    data = c.fetchall()
    conn.close()

    history = []
    for row in data:
        history.append({
            'id': row[0],
            'temp': row[1],
            'timestamp': row[4],
            'status': row[2],
            'model': row[3]
        })

    return jsonify(history)

@app.route('/api/export')
def export_data():
    conn = sqlite3.connect('temperature.db')
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
        download_name=f"thermoscan_export_{datetime.now().date()}.csv"
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)

'''
'''
import os
import sqlite3
import requests
import re
from datetime import datetime
import io
from flask import Flask, render_template, request, jsonify, send_file
from pymongo import MongoClient, DESCENDING
from pymongo.server_api import ServerApi

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Initialize SQLite database (for current session)
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

# MongoDB Atlas setup (for long-term storage)
def get_mongo_client():
    uri = os.getenv('MONGODB_URI')
    if not uri:
        print("MongoDB connection URI not found in environment variables")
        return None
    
    try:
        client = MongoClient(uri, server_api=ServerApi('1'))
        client.admin.command('ping')
        print("Pinged MongoDB Atlas. Connection successful!")
        return client
    except Exception as e:
        print(f"Error connecting to MongoDB: {str(e)}")
        return None

def get_mongo_db():
    client = get_mongo_client()
    return client['thermoscan'] if client else None

def save_to_mongodb(reading):
    """Save reading to MongoDB Atlas for long-term storage"""
    try:
        db = get_mongo_db()
        if db:
            readings_collection = db['readings']
            reading['timestamp'] = datetime.utcnow()
            readings_collection.insert_one(reading)
    except Exception as e:
        print(f"Error saving to MongoDB: {str(e)}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_image():
    try:
        image_data = request.json.get('image')
        model = request.json.get('model', 'gemini')
        gemini_api_key = request.json.get('geminiApiKey')
        together_api_key = request.json.get('togetherApiKey')

        if not image_data:
            return jsonify({'error': 'No image data provided'}), 400

        if model == 'gemini':
            if not gemini_api_key:
                return jsonify({'error': 'Gemini API key not configured'}), 400
            temperature = process_with_gemini(image_data, gemini_api_key)

        elif model == 'together':
            if not together_api_key:
                return jsonify({'error': 'Together AI API key not configured'}), 400
            temperature = process_with_together_ai(image_data, together_api_key)

        else:
            return jsonify({'error': 'Invalid model selected'}), 400

        if temperature > 35:
            status = 'critical'
        elif temperature > 30:
            status = 'warning'
        else:
            status = 'normal'

        timestamp = datetime.now().isoformat()
        
        # Save to SQLite (current session)
        conn = sqlite3.connect('session.db')
        c = conn.cursor()
        c.execute("INSERT INTO readings (temperature, status, model) VALUES (?, ?, ?)",
                  (temperature, status, model))
        conn.commit()
        conn.close()
        
        # Save to MongoDB Atlas (long-term storage)
        save_to_mongodb({
            'temperature': temperature,
            'status': status,
            'model': model
        })

        return jsonify({
            'temperature': temperature,
            'status': status,
            'model': model.capitalize(),
            'timestamp': timestamp
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
    
    # Create the data URL for the image
    image_url = f"data:image/jpeg;base64,{image_data}"
    
    payload = {
        "model": "meta-llama/Llama-Vision-Free",
        "messages": [
            {
                "role": "user",
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

@app.route('/api/history')
def get_history():
    try:
        # Get only current session data from SQLite
        conn = sqlite3.connect('session.db')
        c = conn.cursor()
        c.execute("SELECT * FROM readings ORDER BY timestamp DESC LIMIT 20")
        data = c.fetchall()
        conn.close()

        history = []
        for row in data:
            history.append({
                'id': row[0],
                'temp': row[1],
                'timestamp': row[4],
                'status': row[2],
                'model': row[3]
            })

        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export')
def export_data():
    try:
        # Export from SQLite (current session)
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
        # Export from MongoDB (all historical data)
        db = get_mongo_db()
        if not db:
            return jsonify({'error': 'MongoDB connection not available'}), 500
            
        readings_collection = db['readings']
        data = list(readings_collection.find().sort('timestamp', DESCENDING))
        
        csv = "id,temperature,status,model,timestamp\n"
        for reading in data:
            csv += f"{reading['_id']},{reading['temperature']},{reading['status']},{reading['model']},{reading['timestamp']}\n"

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
'''
'''
import os
import sqlite3
import requests
import re
from datetime import datetime
import io
from flask import Flask, render_template, request, jsonify, send_file
from pymongo import MongoClient, DESCENDING
from pymongo.server_api import ServerApi
from urllib.parse import quote_plus  # For password encoding

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Initialize SQLite database (for current session)
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

# MongoDB Atlas setup with direct credentials
def get_mongo_client():
    # Direct credentials (replace with environment variables in production)
    username = "pk"
    password = "lata@1420"
    cluster = "temperaturemonitoring.w0da5oo"
    dbname = "temp-monitoring"
    
    # Escape special characters in password
    encoded_password = quote_plus(password)
    
    # Construct connection URI
    uri = f"mongodb+srv://{username}:{encoded_password}@{cluster}.mongodb.net/{dbname}?retryWrites=true&w=majority"
    
    try:
        client = MongoClient(uri, server_api=ServerApi('1'))
        client.admin.command('ping')
        print("Pinged MongoDB Atlas. Connection successful!")
        return client
    except Exception as e:
        print(f"Error connecting to MongoDB: {str(e)}")
        return None

def get_mongo_db():
    client = get_mongo_client()
    return client['thermoscan'] if client else None

def save_to_mongodb(reading):
    """Save reading to MongoDB Atlas for long-term storage"""
    try:
        db = get_mongo_db()
        if db:
            readings_collection = db['readings']
            reading['timestamp'] = datetime.utcnow()
            result = readings_collection.insert_one(reading)
            print(f"Saved to MongoDB with id: {result.inserted_id}")
    except Exception as e:
        print(f"Error saving to MongoDB: {str(e)}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/test-mongo')
def test_mongo():
    try:
        db = get_mongo_db()
        if db:
            return jsonify({"status": "success", "collections": db.list_collection_names()})
        return jsonify({"status": "failed"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/process', methods=['POST'])
def process_image():
    try:
        image_data = request.json.get('image')
        model = request.json.get('model', 'gemini')
        gemini_api_key = request.json.get('geminiApiKey')
        together_api_key = request.json.get('togetherApiKey')

        if not image_data:
            return jsonify({'error': 'No image data provided'}), 400

        if model == 'gemini':
            if not gemini_api_key:
                return jsonify({'error': 'Gemini API key not configured'}), 400
            temperature = process_with_gemini(image_data, gemini_api_key)

        elif model == 'together':
            if not together_api_key:
                return jsonify({'error': 'Together AI API key not configured'}), 400
            temperature = process_with_together_ai(image_data, together_api_key)

        else:
            return jsonify({'error': 'Invalid model selected'}), 400

        if temperature > 35:
            status = 'critical'
        elif temperature > 30:
            status = 'warning'
        else:
            status = 'normal'

        timestamp = datetime.now().isoformat()
        
        # Save to SQLite (current session)
        conn = sqlite3.connect('session.db')
        c = conn.cursor()
        c.execute("INSERT INTO readings (temperature, status, model) VALUES (?, ?, ?)",
                  (temperature, status, model))
        conn.commit()
        conn.close()
        
        # Save to MongoDB Atlas (long-term storage)
        save_to_mongodb({
            'temperature': temperature,
            'status': status,
            'model': model
        })

        return jsonify({
            'temperature': temperature,
            'status': status,
            'model': model.capitalize(),
            'timestamp': timestamp
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
    
    # Create the data URL for the image
    image_url = f"data:image/jpeg;base64,{image_data}"
    
    payload = {
        "model": "meta-llama/Llama-Vision-Free",
        "messages": [
            {
                "role": "user",
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

@app.route('/api/history')
def get_history():
    try:
        # Get only current session data from SQLite
        conn = sqlite3.connect('session.db')
        c = conn.cursor()
        c.execute("SELECT * FROM readings ORDER BY timestamp DESC LIMIT 20")
        data = c.fetchall()
        conn.close()

        history = []
        for row in data:
            history.append({
                'id': row[0],
                'temp': row[1],
                'timestamp': row[4],
                'status': row[2],
                'model': row[3]
            })

        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export')
def export_data():
    try:
        # Export from SQLite (current session)
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
        # Export from MongoDB (all historical data)
        db = get_mongo_db()
        if not db:
            return jsonify({'error': 'MongoDB connection not available'}), 500
            
        readings_collection = db['readings']
        data = list(readings_collection.find().sort('timestamp', DESCENDING))
        
        csv = "id,temperature,status,model,timestamp\n"
        for reading in data:
            # Convert ObjectId to string and format timestamp
            csv += f"{str(reading['_id'])},{reading['temperature']},{reading['status']},{reading['model']},{reading['timestamp']}\n"

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)'''



import os
import sqlite3
import requests
import re
from datetime import datetime
import io
from flask import Flask, render_template, request, jsonify, send_file
from pymongo import MongoClient, DESCENDING
from pymongo.server_api import ServerApi
from urllib.parse import quote_plus

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

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
        c.execute("INSERT INTO readings (temperature, status, model) VALUES (?, ?, ?)",
                (temperature, status, model))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"SQLite Save Error: {str(e)}")
        return False

# MongoDB Connection with Robust Error Handling
def get_mongo_client():
    # MongoDB Atlas configuration
    username = "pk"
    password = "lata@1420"
    cluster = "temperaturemonitoring.w0da5oo"
    dbname = "temp-monitoring"
    
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
            'timestamp': datetime.utcnow(),
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
        image_data = request.json.get('image')
        model = request.json.get('model', 'gemini')
        gemini_api_key = request.json.get('geminiApiKey')
        together_api_key = request.json.get('togetherApiKey')

        if not image_data:
            return jsonify({'error': 'No image data provided'}), 400

        if model == 'gemini':
            if not gemini_api_key:
                return jsonify({'error': 'Gemini API key not configured'}), 400
            temperature = process_with_gemini(image_data, gemini_api_key)

        elif model == 'together':
            if not together_api_key:
                return jsonify({'error': 'Together AI API key not configured'}), 400
            temperature = process_with_together_ai(image_data, together_api_key)

        else:
            return jsonify({'error': 'Invalid model selected'}), 400

        if temperature > 35:
            status = 'critical'
        elif temperature > 30:
            status = 'warning'
        else:
            status = 'normal'

        # Save to both databases
        sqlite_success = save_to_sqlite(temperature, status, model)
        mongo_success = save_to_mongodb({
            'temperature': temperature,
            'status': status,
            'model': model
        })

        return jsonify({
            'temperature': temperature,
            'status': status,
            'model': model.capitalize(),
            'timestamp': datetime.now().isoformat(),
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
                "role": "user",
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
            history.append({
                'id': row[0],
                'temp': row[1],
                'timestamp': row[4],
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
            csv += f"{reading['_id']},{reading['temperature']},{reading['status']},{reading['model']},{reading['timestamp']},{reading.get('source', '')}\n"

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
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)