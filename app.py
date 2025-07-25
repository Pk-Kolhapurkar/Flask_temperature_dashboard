import os
import sqlite3
import random
from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Database setup
def init_db():
    conn = sqlite3.connect('temperature.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS readings
                 (id INTEGER PRIMARY KEY, 
                 temperature REAL, 
                 status TEXT,
                 model TEXT,
                 timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_image():
    try:
        # Simulate temperature reading (replace with actual AI processing)
        model = request.json.get('model', 'gemini')
        
        # Generate realistic temperature values
        base_temp = 25.0 if model == 'gemini' else 26.0
        temperature = round(base_temp + random.uniform(-2, 5), 1)
        
        # Determine status
        if temperature > 35:
            status = 'critical'
        elif temperature > 30:
            status = 'warning'
        else:
            status = 'normal'
        
        # Save to database
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
    app.run(debug=True)