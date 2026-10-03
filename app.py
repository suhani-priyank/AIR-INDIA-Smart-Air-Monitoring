from flask import Flask, request, jsonify, render_template, send_file, redirect, url_for, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import csv
import io
import random
import math

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'air_quality.db'

app = Flask(__name__)
app.secret_key = 'change-this-secret-in-production'
CORS(app)

# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'citizen',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS states (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );

    CREATE TABLE IF NOT EXISTS cities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        UNIQUE(state_id, name),
        FOREIGN KEY(state_id) REFERENCES states(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS stations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'online',
        last_seen TEXT,
        FOREIGN KEY(city_id) REFERENCES cities(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        mq2 REAL DEFAULT 0,
        mq3 REAL DEFAULT 0,
        mq135 REAL DEFAULT 0,
        pm25 REAL DEFAULT 0,
        pm10 REAL DEFAULT 0,
        no2 REAL DEFAULT 0,
        so2 REAL DEFAULT 0,
        co REAL DEFAULT 0,
        o3 REAL DEFAULT 0,
        temperature REAL DEFAULT 0,
        humidity REAL DEFAULT 0,
        wind_speed REAL DEFAULT 0,
        aqi INTEGER DEFAULT 0,
        status TEXT DEFAULT 'Waiting',
        FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_id INTEGER NOT NULL,
        alert_type TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
    );
    ''')
    seed_locations(conn)
    seed_admin(conn)
    seed_demo_readings(conn)
    conn.commit()
    conn.close()


def seed_locations(conn):
    data = {
        'Delhi': [('Delhi', 28.6139, 77.2090)],
        'Maharashtra': [('Mumbai', 19.0760, 72.8777), ('Pune', 18.5204, 73.8567), ('Nagpur', 21.1458, 79.0882)],
        'Odisha': [('Bhubaneswar', 20.2961, 85.8245), ('Rourkela', 22.2604, 84.8536), ('Cuttack', 20.4625, 85.8828), ('Sambalpur', 21.4669, 83.9812)],
        'Bihar': [('Patna', 25.5941, 85.1376), ('Gaya', 24.7914, 85.0002), ('Muzaffarpur', 26.1209, 85.3647)],
        'Karnataka': [('Bengaluru', 12.9716, 77.5946), ('Mysuru', 12.2958, 76.6394)],
        'West Bengal': [('Kolkata', 22.5726, 88.3639), ('Durgapur', 23.5204, 87.3119)],
        'Tamil Nadu': [('Chennai', 13.0827, 80.2707), ('Coimbatore', 11.0168, 76.9558)],
        'Telangana': [('Hyderabad', 17.3850, 78.4867)],
        'Gujarat': [('Ahmedabad', 23.0225, 72.5714), ('Surat', 21.1702, 72.8311)],
        'Rajasthan': [('Jaipur', 26.9124, 75.7873), ('Udaipur', 24.5854, 73.7125)],
        'Uttar Pradesh': [('Lucknow', 26.8467, 80.9462), ('Kanpur', 26.4499, 80.3319), ('Varanasi', 25.3176, 82.9739)],
        'Jharkhand': [('Ranchi', 23.3441, 85.3096), ('Jamshedpur', 22.8046, 86.2029)],
        'Punjab': [('Ludhiana', 30.9010, 75.8573), ('Amritsar', 31.6340, 74.8723)],
        'Haryana': [('Gurugram', 28.4595, 77.0266), ('Faridabad', 28.4089, 77.3178)],
        'Kerala': [('Kochi', 9.9312, 76.2673), ('Thiruvananthapuram', 8.5241, 76.9366)],
    }
    for state, cities in data.items():
        conn.execute('INSERT OR IGNORE INTO states(name) VALUES(?)', (state,))
        state_id = conn.execute('SELECT id FROM states WHERE name=?', (state,)).fetchone()['id']
        for city, lat, lon in cities:
            conn.execute('INSERT OR IGNORE INTO cities(state_id,name,latitude,longitude) VALUES(?,?,?,?)', (state_id, city, lat, lon))
            city_id = conn.execute('SELECT id FROM cities WHERE state_id=? AND name=?', (state_id, city)).fetchone()['id']
            existing = conn.execute('SELECT COUNT(*) AS n FROM stations WHERE city_id=?', (city_id,)).fetchone()['n']
            if not existing:
                for idx, offset in enumerate([(0,0), (0.015,0.012), (-0.012,0.018)], 1):
                    conn.execute('''INSERT INTO stations(city_id,name,latitude,longitude,status,last_seen)
                                    VALUES(?,?,?,?,?,?)''',
                                 (city_id, f'{city} Station {idx}', lat+offset[0], lon+offset[1], 'online', datetime.now().isoformat(timespec='seconds')))


def seed_admin(conn):
    if not conn.execute('SELECT 1 FROM users WHERE email=?', ('admin@airindia.local',)).fetchone():
        conn.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',
                     ('System Admin', 'admin@airindia.local', generate_password_hash('admin123'), 'admin'))


def seed_demo_readings(conn):
    count = conn.execute('SELECT COUNT(*) AS n FROM readings').fetchone()['n']
    if count:
        return
    stations = conn.execute('SELECT id FROM stations').fetchall()
    now = datetime.now()
    for st in stations:
        base = random.randint(55, 190)
        for h in range(48, 0, -1):
            t = now - timedelta(hours=h)
            pm25 = max(8, base * 0.35 + random.uniform(-12, 18))
            pm10 = max(15, base * 0.65 + random.uniform(-20, 30))
            no2 = max(5, base * 0.18 + random.uniform(-8, 10))
            so2 = max(3, base * 0.10 + random.uniform(-5, 8))
            co = max(0.2, base / 120 + random.uniform(-0.2, 0.5))
            o3 = max(5, base * 0.16 + random.uniform(-8, 10))
            aqi, status = calculate_aqi(pm25, pm10, no2, so2, co, o3)
            conn.execute('''INSERT INTO readings
                (station_id,timestamp,mq2,mq3,mq135,pm25,pm10,no2,so2,co,o3,temperature,humidity,wind_speed,aqi,status)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (st['id'], t.isoformat(timespec='seconds'), random.randint(100,900), random.randint(100,700), random.randint(100,1200),
                 round(pm25,1), round(pm10,1), round(no2,1), round(so2,1), round(co,2), round(o3,1),
                 round(random.uniform(22,34),1), round(random.uniform(35,85),1), round(random.uniform(0.5,7),1), aqi, status))

# ---------------- AQI ----------------

BREAKPOINTS = {
    'pm25': [(0,30,0,50),(31,60,51,100),(61,90,101,200),(91,120,201,300),(121,250,301,400),(251,500,401,500)],
    'pm10': [(0,50,0,50),(51,100,51,100),(101,250,101,200),(251,350,201,300),(351,430,301,400),(431,600,401,500)],
    'no2': [(0,40,0,50),(41,80,51,100),(81,180,101,200),(181,280,201,300),(281,400,301,400),(401,800,401,500)],
    'so2': [(0,40,0,50),(41,80,51,100),(81,380,101,200),(381,800,201,300),(801,1600,301,400),(1601,2500,401,500)],
    'co': [(0,1,0,50),(1.1,2,51,100),(2.1,10,101,200),(10.1,17,201,300),(17.1,34,301,400),(34.1,50,401,500)],
    'o3': [(0,50,0,50),(51,100,51,100),(101,168,101,200),(169,208,201,300),(209,748,301,400),(749,1000,401,500)]
}


def sub_index(value, ranges):
    for c_low, c_high, i_low, i_high in ranges:
        if c_low <= value <= c_high:
            return round(((i_high-i_low)/(c_high-c_low))*(value-c_low)+i_low)
    return 500 if value > ranges[-1][1] else 0


def calculate_aqi(pm25=0, pm10=0, no2=0, so2=0, co=0, o3=0):
    values = {'pm25': pm25, 'pm10': pm10, 'no2': no2, 'so2': so2, 'co': co, 'o3': o3}
    indices = [sub_index(float(v), BREAKPOINTS[k]) for k,v in values.items() if float(v) > 0]
    aqi = max(indices) if indices else 0
    return min(500, aqi), aqi_status(aqi)


def aqi_status(aqi):
    if aqi <= 50: return 'Good'
    if aqi <= 100: return 'Satisfactory'
    if aqi <= 200: return 'Moderate'
    if aqi <= 300: return 'Poor'
    if aqi <= 400: return 'Very Poor'
    return 'Severe'


def aqi_message(aqi):
    if aqi <= 50: return 'Air quality is good with low health risk.'
    if aqi <= 100: return 'Air quality is satisfactory for most people.'
    if aqi <= 200: return 'Sensitive people should consider reducing prolonged outdoor exposure.'
    if aqi <= 300: return 'Reduce prolonged outdoor activity and follow local advisories.'
    if aqi <= 400: return 'Avoid prolonged outdoor exposure, especially for sensitive groups.'
    return 'Severe pollution conditions. Follow official health advisories.'

# ---------------- API ----------------

@app.route('/')
def home():
    return redirect(url_for('dashboard')) if 'user' in session else redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', user=session.get('user'))

@app.route('/api/states')
def states():
    conn = get_db(); rows = conn.execute('SELECT id,name FROM states ORDER BY name').fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/cities/<int:state_id>')
def cities(state_id):
    conn = get_db(); rows = conn.execute('SELECT id,name,latitude,longitude FROM cities WHERE state_id=? ORDER BY name', (state_id,)).fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/stations/<int:city_id>')
def stations(city_id):
    conn = get_db(); rows = conn.execute('SELECT id,name,latitude,longitude,status,last_seen FROM stations WHERE city_id=? ORDER BY name', (city_id,)).fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/map')
def map_data():
    conn = get_db()
    rows = conn.execute('''
        SELECT s.id,s.name,s.latitude,s.longitude,s.status,s.last_seen,c.name city,st.name state,
               r.aqi,r.status aqi_status,r.timestamp
        FROM stations s JOIN cities c ON c.id=s.city_id JOIN states st ON st.id=c.state_id
        LEFT JOIN readings r ON r.id=(SELECT id FROM readings x WHERE x.station_id=s.id ORDER BY x.id DESC LIMIT 1)
        ORDER BY st.name,c.name,s.name
    ''').fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/latest/<int:station_id>')
def latest(station_id):
    conn = get_db()
    row = conn.execute('''SELECT r.*,s.name station,c.name city,st.name state,s.latitude station_lat,s.longitude station_lon
                          FROM readings r JOIN stations s ON s.id=r.station_id JOIN cities c ON c.id=s.city_id JOIN states st ON st.id=c.state_id
                          WHERE r.station_id=? ORDER BY r.id DESC LIMIT 1''', (station_id,)).fetchone()
    conn.close()
    if not row: return jsonify({'error':'No reading found'}), 404
    return jsonify(dict(row) | {'message': aqi_message(row['aqi'])})

@app.route('/api/history/<int:station_id>')
def history(station_id):
    limit = min(int(request.args.get('limit', 100)), 500)
    conn = get_db(); rows = conn.execute('SELECT * FROM readings WHERE station_id=? ORDER BY id DESC LIMIT ?', (station_id,limit)).fetchall(); conn.close()
    return jsonify([dict(r) for r in reversed(rows)])

@app.route('/api/summary')
def summary():
    conn = get_db()
    totals = conn.execute('SELECT (SELECT COUNT(*) FROM states) states,(SELECT COUNT(*) FROM cities) cities,(SELECT COUNT(*) FROM stations) stations,(SELECT COUNT(*) FROM stations WHERE status="online") online_stations').fetchone()
    latest_rows = conn.execute('''SELECT r.aqi,r.status,s.name station,c.name city,st.name state
                                  FROM readings r JOIN stations s ON s.id=r.station_id JOIN cities c ON c.id=s.city_id JOIN states st ON st.id=c.state_id
                                  WHERE r.id IN (SELECT MAX(id) FROM readings GROUP BY station_id)''').fetchall()
    cats = {'Good':0,'Satisfactory':0,'Moderate':0,'Poor':0,'Very Poor':0,'Severe':0}
    for r in latest_rows: cats[r['status']] = cats.get(r['status'],0)+1
    highest = sorted([dict(r) for r in latest_rows], key=lambda x:x['aqi'], reverse=True)[:5]
    lowest = sorted([dict(r) for r in latest_rows], key=lambda x:x['aqi'])[:5]
    conn.close()
    return jsonify({'totals':dict(totals),'categories':cats,'highest':highest,'lowest':lowest})

@app.route('/api/compare')
def compare():
    ids = [int(x) for x in request.args.get('stations','').split(',') if x.isdigit()][:5]
    if not ids: return jsonify([])
    conn=get_db(); placeholders=','.join('?'*len(ids))
    rows=conn.execute(f'''SELECT r.*,s.name station,c.name city,st.name state FROM readings r
        JOIN stations s ON s.id=r.station_id JOIN cities c ON c.id=s.city_id JOIN states st ON st.id=c.state_id
        WHERE r.id IN (SELECT MAX(id) FROM readings GROUP BY station_id) AND r.station_id IN ({placeholders})''', ids).fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/predict/<int:station_id>')
def predict(station_id):
    conn=get_db(); rows=conn.execute('SELECT aqi,pm25,pm10,temperature,humidity FROM readings WHERE station_id=? ORDER BY id DESC LIMIT 24',(station_id,)).fetchall(); conn.close()
    if not rows: return jsonify({'error':'No history'}),404
    aqis=[r['aqi'] for r in rows]
    recent=aqis[:6]
    slope=(recent[0]-recent[-1])/max(1,len(recent)-1) if len(recent)>1 else 0
    current=aqis[0]
    predictions=[]
    for h in range(1,7):
        value=max(0,min(500,round(current+slope*h)))
        predictions.append({'hours_ahead':h,'predicted_aqi':value,'status':aqi_status(value)})
    return jsonify({'method':'trend-based baseline (replace with trained Random Forest/LSTM for production)','current_aqi':current,'predictions':predictions})

@app.route('/api/alerts')
def alerts():
    conn=get_db(); rows=conn.execute('''SELECT a.*,s.name station,c.name city,st.name state FROM alerts a
        JOIN stations s ON s.id=a.station_id JOIN cities c ON c.id=s.city_id JOIN states st ON st.id=c.state_id
        ORDER BY a.id DESC LIMIT 20''').fetchall(); conn.close(); return jsonify([dict(r) for r in rows])

@app.route('/data', methods=['POST'])
def receive_data():
    """IoT endpoint. Send station_id plus pollutant/environment values as form or JSON."""
    try:
        payload = request.get_json(silent=True) or request.form
        station_id = int(payload.get('station_id', 1))
        values = {k: float(payload.get(k, 0) or 0) for k in ['mq2','mq3','mq135','pm25','pm10','no2','so2','co','o3','temperature','humidity','wind_speed']}
        aqi, status = calculate_aqi(values['pm25'], values['pm10'], values['no2'], values['so2'], values['co'], values['o3'])
        now = datetime.now().isoformat(timespec='seconds')
        conn=get_db()
        conn.execute('''INSERT INTO readings(station_id,timestamp,mq2,mq3,mq135,pm25,pm10,no2,so2,co,o3,temperature,humidity,wind_speed,aqi,status)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                     (station_id,now,values['mq2'],values['mq3'],values['mq135'],values['pm25'],values['pm10'],values['no2'],values['so2'],values['co'],values['o3'],values['temperature'],values['humidity'],values['wind_speed'],aqi,status))
        conn.execute('UPDATE stations SET last_seen=?,status="online" WHERE id=?',(now,station_id))
        if aqi >= 200:
            conn.execute('INSERT INTO alerts(station_id,alert_type,message,timestamp) VALUES(?,?,?,?)', (station_id,'AQI Alert',f'AQI reached {aqi} ({status}). {aqi_message(aqi)}',now))
        conn.commit(); conn.close()
        return jsonify({'message':'Reading stored','aqi':aqi,'status':status,'timestamp':now})
    except Exception as e:
        return jsonify({'error':str(e)}),400


# ---------------- SMART ANALYTICS ----------------

def latest_reading(conn, station_id):
    return conn.execute("SELECT * FROM readings WHERE station_id=? ORDER BY id DESC LIMIT 1", (station_id,)).fetchone()

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

@app.route('/api/smart/<int:station_id>')
def smart_features(station_id):
    conn = get_db()
    latest = latest_reading(conn, station_id)
    rows = conn.execute("SELECT * FROM readings WHERE station_id=? ORDER BY id DESC LIMIT 24", (station_id,)).fetchall()
    conn.close()
    if not latest:
        return jsonify({'error': 'No reading found'}), 404
    current = dict(latest)
    history = [dict(r) for r in rows]

    anomaly = []
    health = {}
    for key in ('mq2', 'mq3', 'mq135'):
        vals = [safe_float(r.get(key)) for r in history[1:] if r.get(key) is not None]
        value = safe_float(current.get(key))
        mean = sum(vals) / len(vals) if vals else value
        variance = sum((x - mean) ** 2 for x in vals) / len(vals) if vals else 0
        sd = math.sqrt(variance)
        z = abs(value - mean) / sd if sd > 0 else 0
        spike = z >= 2.5 and len(vals) >= 5
        flat = len(vals) >= 6 and max(vals[-6:]) - min(vals[-6:]) <= max(2, abs(mean) * 0.01)
        health[key] = max(45, min(100, round(100 - min(55, z * 15) - (12 if flat else 0))))
        if spike:
            anomaly.append({'sensor': key.upper(), 'value': round(value, 2), 'z_score': round(z, 2), 'type': 'unusual spike'})
        elif flat:
            anomaly.append({'sensor': key.upper(), 'value': round(value, 2), 'z_score': 0, 'type': 'low variation / calibration check'})

    overall_health = round(sum(health.values()) / len(health)) if health else 0

    aqi = safe_float(current.get('aqi'))
    weather_factor = 0
    if safe_float(current.get('wind_speed')) >= 4:
        weather_factor += 4
    if safe_float(current.get('humidity')) < 80:
        weather_factor += 2
    sensor_factor = min(8, overall_health * 0.08)
    airsafe = max(0, min(100, round(100 - aqi * 0.13 + weather_factor + sensor_factor)))
    airsafe_status = 'Relatively Safe' if airsafe >= 75 else ('Use Caution' if airsafe >= 50 else 'High Exposure')

    buckets = {}
    for r in history:
        hour = datetime.fromisoformat(r['timestamp']).hour
        buckets.setdefault(hour, []).append(safe_float(r['aqi']))
    best = [{'hour': h, 'avg_aqi': round(sum(v)/len(v))} for h,v in buckets.items()]
    best.sort(key=lambda x: x['avg_aqi'])
    best_windows = [{'label': f"{x['hour']:02d}:00–{(x['hour']+1)%24:02d}:00", 'avg_aqi': x['avg_aqi']} for x in best[:3]]

    events = []
    for key in ('mq2', 'mq3', 'mq135'):
        vals = [safe_float(r.get(key)) for r in history[1:7]]
        value = safe_float(current.get(key))
        baseline = sum(vals) / len(vals) if vals else value
        change = ((value - baseline) / baseline * 100) if baseline else 0
        if change >= 25:
            events.append({'sensor': key.upper(), 'change_percent': round(change, 1), 'severity': 'High'})
        elif change >= 15:
            events.append({'sensor': key.upper(), 'change_percent': round(change, 1), 'severity': 'Moderate'})

    previous = [safe_float(r['aqi']) for r in history[1:7]]
    prev_avg = sum(previous) / len(previous) if previous else aqi
    trend = 'increasing' if aqi > prev_avg * 1.05 else ('decreasing' if aqi < prev_avg * 0.95 else 'stable')
    explanation = {
        'aqi': int(aqi),
        'status': current.get('status') or aqi_status(aqi),
        'trend': trend,
        'recent_average': round(prev_avg),
        'message': f"The current AQI is {int(aqi)} and the recent trend is {trend}. MQ sensor readings and local environmental conditions are used as supporting signals in this project."
    }

    return jsonify({
        'airsafe': {'score': airsafe, 'status': airsafe_status},
        'sensor_health': {'mq2': health.get('mq2', 0), 'mq3': health.get('mq3', 0), 'mq135': health.get('mq135', 0), 'overall': overall_health},
        'anomalies': anomaly,
        'events': events,
        'best_windows': best_windows,
        'explanation': explanation
    })

@app.route('/api/assistant', methods=['POST'])
def assistant():
    payload = request.get_json(silent=True) or {}
    question = str(payload.get('question', '')).strip().lower()
    station_id = int(payload.get('station_id', 0) or 0)
    conn = get_db()
    row = latest_reading(conn, station_id) if station_id else None
    station = None
    if station_id:
        station = conn.execute("SELECT s.name,c.name city,st.name state FROM stations s JOIN cities c ON c.id=s.city_id JOIN states st ON st.id=c.state_id WHERE s.id=?", (station_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'answer': 'Please select a monitoring station first.'})
    aqi = int(row['aqi'] or 0)
    status = row['status'] or aqi_status(aqi)
    location = f"{station['name']}, {station['city']}" if station else 'the selected station'
    if any(k in question for k in ('safe', 'outside', 'outdoor', 'go out')):
        answer = f"{location} currently reports AQI {aqi} ({status}). Check the Best Time and AirSafe cards before making an outdoor decision."
    elif any(k in question for k in ('why', 'reason', 'explain', 'aqi')):
        answer = f"{location} currently has AQI {aqi} ({status}). The dashboard compares the current reading with recent history and MQ2, MQ3 and MQ135 patterns to explain changes."
    elif any(k in question for k in ('sensor', 'mq2', 'mq3', 'mq135')):
        answer = f"Current sensor values at {location}: MQ2={row['mq2']:.1f}, MQ3={row['mq3']:.1f}, MQ135={row['mq135']:.1f}. Use Sensor Health and Anomaly Detection for quality checks."
    elif any(k in question for k in ('compare', 'city')):
        answer = "Use Sensor Comparison to select up to five stations and compare AQI, MQ2, MQ3 and MQ135 side by side."
    else:
        answer = f"I can help with {location}'s AQI, sensor readings, anomalies, AirSafe Score, best outdoor times and station comparison. Try: Is it safe to go outside?"
    return jsonify({'answer': answer, 'station': location, 'aqi': aqi, 'status': status})

@app.route('/api/route_score')
def route_score():
    conn = get_db()
    rows = conn.execute("""SELECT s.latitude,s.longitude,s.name,c.name city,st.name state,r.aqi
                          FROM stations s JOIN cities c ON c.id=s.city_id JOIN states st ON st.id=c.state_id
                          LEFT JOIN readings r ON r.id=(SELECT id FROM readings x WHERE x.station_id=s.id ORDER BY x.id DESC LIMIT 1)""").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/download_csv')
def download_csv():
    conn=get_db(); rows=conn.execute('''SELECT r.*,s.name station,c.name city,st.name state FROM readings r
        JOIN stations s ON s.id=r.station_id JOIN cities c ON c.id=s.city_id JOIN states st ON st.id=c.state_id ORDER BY r.timestamp DESC''').fetchall(); conn.close()
    output=io.StringIO(); writer=csv.writer(output)
    if rows: writer.writerow(rows[0].keys()); [writer.writerow(list(r)) for r in rows]
    else: writer.writerow(['No data'])
    data=io.BytesIO(output.getvalue().encode('utf-8')); data.seek(0)
    return send_file(data,mimetype='text/csv',as_attachment=True,download_name='pan_india_air_quality.csv')

# ---------------- AUTH ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        conn=get_db(); user=conn.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); conn.close()
        if user and check_password_hash(user['password_hash'],password):
            session['user']={'id':user['id'],'name':user['name'],'email':user['email'],'role':user['role']}
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='Invalid email or password')
    return render_template('login.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method=='POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        if not name or not email or len(password)<6: return render_template('signup.html',error='Enter all fields. Password must be at least 6 characters.')
        try:
            conn=get_db(); conn.execute('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',(name,email,generate_password_hash(password))); conn.commit(); conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('signup.html',error='Email already registered.')
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

@app.context_processor
def inject_user():
    return {'current_user':session.get('user')}

init_db()

if __name__=='__main__':
    app.run(host='0.0.0.0',port=5000,debug=True)
