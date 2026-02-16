from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin  # Add cross_origin import
from datetime import datetime, timedelta
import json
import sqlite3
import re

app = Flask(__name__)

# FIX: Change this line to allow all origins
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow ALL origins

# OR for more specific control:
# CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:5000", 
#                    "http://10.0.2.2:5000", "http://192.168.*.*"]) 

# Optional: Add after_request handler for extra CORS headers
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# Initialize database
def init_db():
    conn = sqlite3.connect('period_tracker.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            last_period_date TEXT,
            cycle_length INTEGER DEFAULT 28,
            period_duration INTEGER DEFAULT 5,
            created_at TEXT
        )
    ''')
    
    # Create chat history table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            user_message TEXT,
            bot_response TEXT,
            timestamp TEXT
        )
    ''')
    
    # Create symptoms log table
    c.execute('''
        CREATE TABLE IF NOT EXISTS symptoms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            symptom TEXT,
            severity TEXT,
            date TEXT,
            notes TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

class PeriodTrackerChatbot:
    def __init__(self):
        self.intent_patterns = {
            'greeting': [
                r'hello', r'hi', r'hey', r'good morning', r'good afternoon'
            ],
            'period_start': [
                r'period (started|began)', r'start(ed|ing) (my )?period',
                r'got my period', r'my period (started|began)',
                r'menstruation (started|began)', r'period date today',
                r'log period (today|now)'
            ],
            'period_end': [
                r'period (ended|finished|stopped)', r'end(ed|ing) (my )?period'
            ],
            'next_period': [
                r'when (is|will be) my next period', r'next period date',
                r'predict my period', r'when (should|will) i get my period',
                r'period prediction'
            ],
            'symptoms': [
                r'(cramps|headache|bloating|pain|tired|fatigue|nausea)',
                r'i have (.*) pain', r'feeling (.*)',
                r'symptom(s)?', r'i feel (.*)',
                r'logging symptoms', r'log symptom'
            ],
            'cycle_info': [
                r'my cycle length', r'average cycle', r'cycle days',
                r'how long is my cycle'
            ],
            'pms': [
                r'what is pms', r'premenstrual syndrome',
                r'pms symptoms', r'before period symptoms'
            ],
            'pain_relief': [
                r'how to (relieve|reduce|stop) (pain|cramps)',
                r'pain relief', r'cramp relief',
                r'what helps with (cramps|pain)'
            ],
            'ovulation': [
                r'when do i ovulate', r'ovulation (date|time)',
                r'fertile window', r'ovulation calculator'
            ],
            'set_reminder': [
                r'set reminder', r'remind me', r'notification',
                r'alert me before period'
            ]
        }
    
    def detect_intent(self, message):
        """Detect user intent from message"""
        message_lower = message.lower()
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return intent
        
        return 'unknown'
    
    def calculate_next_period(self, last_period_date, cycle_length=28):
        """Calculate next period date"""
        try:
            last_date = datetime.strptime(last_period_date, '%Y-%m-%d')
            next_date = last_date + timedelta(days=cycle_length)
            return next_date.strftime('%Y-%m-%d')
        except:
            return None
    
    def calculate_ovulation(self, last_period_date, cycle_length=28):
        """Calculate ovulation date (typically 14 days before next period)"""
        try:
            last_date = datetime.strptime(last_period_date, '%Y-%m-%d')
            ovulation_date = last_date + timedelta(days=cycle_length - 14)
            return ovulation_date.strftime('%Y-%m-%d')
        except:
            return None
    
    def process_message(self, message, user_id):
        """Process user message and generate response"""
        intent = self.detect_intent(message)
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Connect to database
        conn = sqlite3.connect('period_tracker.db')
        c = conn.cursor()
        
        # Get user data
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_data = c.fetchone()
        
        response = ""
        actions = []
        
        if intent == 'greeting':
            response = "👋 Hello! I'm your Period Tracking Assistant. I can help you:\n• Log period start/end dates\n• Predict your next period\n• Track symptoms\n• Calculate ovulation\n• Answer questions about menstrual health\n\nHow can I help you today?"
        
        elif intent == 'period_start':
            # Update last period date in database
            c.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, last_period_date, created_at) 
                VALUES (?, ?, ?)
            ''', (user_id, today, today))
            
            conn.commit()
            
            # Calculate next period
            c.execute("SELECT cycle_length FROM users WHERE user_id = ?", (user_id,))
            cycle_data = c.fetchone()
            cycle_length = cycle_data[0] if cycle_data and cycle_data[0] else 28
            
            next_period = self.calculate_next_period(today, cycle_length)
            
            response = f"✅ I've logged that your period started today ({today}).\n\n"
            if next_period:
                response += f"📅 Your next period is predicted to start around **{next_period}**.\n"
                ovulation_date = self.calculate_ovulation(today, cycle_length)
                if ovulation_date:
                    response += f"🥚 Your estimated ovulation date is around **{ovulation_date}**.\n\n"
            response += "Would you like to log any symptoms?"
            
            actions = ["Log symptoms", "Set reminder", "Calculate ovulation"]
        
        elif intent == 'next_period':
            if user_data and user_data[1]:  # if last_period_date exists
                last_period = user_data[1]
                cycle_length = user_data[2] if user_data[2] else 28
                
                next_period = self.calculate_next_period(last_period, cycle_length)
                
                if next_period:
                    days_until = (datetime.strptime(next_period, '%Y-%m-%d') - datetime.now()).days
                    response = f"Based on your last period on **{last_period}**:\n\n"
                    response += f"📅 **Next period:** {next_period}\n"
                    response += f"⏳ **Days until:** {days_until} days\n\n"
                    
                    # Calculate fertile window
                    ovulation_date = self.calculate_ovulation(last_period, cycle_length)
                    if ovulation_date:
                        ovulation_date_obj = datetime.strptime(ovulation_date, '%Y-%m-%d')
                        fertile_start = (ovulation_date_obj - timedelta(days=3)).strftime('%Y-%m-%d')
                        fertile_end = (ovulation_date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
                        
                        response += f"🥚 **Estimated ovulation:** {ovulation_date}\n"
                        response += f"🌡️ **Fertile window:** {fertile_start} to {fertile_end}"
                else:
                    response = "I couldn't calculate your next period. Please log your period start date first."
            else:
                response = "I don't have your period history yet. Please tell me when your period started (e.g., 'My period started today')."
        
        elif intent == 'symptoms':
            # Extract symptoms from message
            symptoms_keywords = ['cramps', 'headache', 'bloating', 'back pain', 'breast tenderness', 
                                'mood swings', 'fatigue', 'nausea', 'acne', 'food cravings']
            
            detected_symptoms = []
            for symptom in symptoms_keywords:
                if symptom in message.lower():
                    detected_symptoms.append(symptom)
            
            if detected_symptoms:
                # Log symptoms to database
                for symptom in detected_symptoms:
                    c.execute('''
                        INSERT INTO symptoms (user_id, symptom, date, severity)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, symptom, today, 'moderate'))
                
                conn.commit()
                
                response = f"✅ I've logged your symptoms: {', '.join(detected_symptoms)}\n\n"
                response += "💡 **Tips for relief:**\n"
                
                if 'cramps' in detected_symptoms:
                    response += "• Apply heat pad to lower abdomen\n• Gentle exercise or walking\n• Over-the-counter pain relievers\n• Drink warm herbal tea\n"
                if 'headache' in detected_symptoms:
                    response += "• Stay hydrated\n• Rest in a dark room\n• Cold compress on forehead\n• Avoid caffeine\n"
                if 'bloating' in detected_symptoms:
                    response += "• Reduce salt intake\n• Drink plenty of water\n• Eat smaller, frequent meals\n• Avoid carbonated drinks\n"
                
                response += "\nWould you like to set a reminder for pain medication?"
            else:
                response = "I can help you log symptoms like cramps, headache, bloating, mood swings, etc. What symptoms are you experiencing?"
                actions = ["Cramps", "Headache", "Bloating", "Mood swings", "Fatigue"]
        
        elif intent == 'pms':
            response = """**Premenstrual Syndrome (PMS)** refers to physical and emotional symptoms that occur 1-2 weeks before your period.

**Common symptoms include:**
• Mood swings, irritability, or depression
• Bloating and weight gain
• Breast tenderness
• Fatigue
• Food cravings
• Headaches
• Acne

**Management tips:**
1. **Exercise regularly** - even light activity helps
2. **Balanced diet** - reduce salt, sugar, and caffeine
3. **Stress management** - yoga, meditation, deep breathing
4. **Adequate sleep** - 7-9 hours per night
5. **Over-the-counter** pain relievers if needed

Symptoms usually improve within a few days of starting your period."""
        
        elif intent == 'pain_relief':
            response = """**Period Pain Relief Methods:**

**Immediate Relief:**
1. **Heat therapy** - Hot water bottle or heating pad on abdomen
2. **OTC medication** - Ibuprofen, Naproxen (take at first sign)
3. **Gentle massage** - Circular motions on lower abdomen

**Lifestyle Changes:**
• **Regular exercise** - Increases endorphins
• **Warm baths** - Relaxes muscles
• **Dietary changes**:
  - Omega-3 fatty acids (fish, flaxseed)
  - Reduce caffeine and alcohol
  - Magnesium-rich foods (nuts, leafy greens)
• **Hydration** - Drink plenty of water

**Alternative Therapies:**
• Acupuncture/acupressure
• Herbal teas (ginger, chamomile)
• Yoga stretches (child's pose, cat-cow)

**When to see a doctor:**
• Pain prevents normal activities
• Symptoms worsen over time
• Heavy bleeding with clots
• Pain with fever"""

        elif intent == 'ovulation':
            if user_data and user_data[1]:
                last_period = user_data[1]
                cycle_length = user_data[2] if user_data[2] else 28
                
                ovulation_date = self.calculate_ovulation(last_period, cycle_length)
                
                if ovulation_date:
                    ovulation_date_obj = datetime.strptime(ovulation_date, '%Y-%m-%d')
                    fertile_start = (ovulation_date_obj - timedelta(days=3)).strftime('%Y-%m-%d')
                    fertile_end = (ovulation_date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
                    
                    response = f"**Ovulation Calculation:**\n\n"
                    response += f"📅 Last period: {last_period}\n"
                    response += f"🔄 Cycle length: {cycle_length} days\n"
                    response += f"🥚 **Estimated ovulation:** {ovulation_date}\n"
                    response += f"🌡️ **Fertile window:** {fertile_start} to {fertile_end}\n\n"
                    response += "**Ovulation signs to watch for:**\n"
                    response += "• Egg-white cervical mucus\n• Mild pelvic pain (mittelschmerz)\n• Slight rise in basal body temperature\n• Increased libido\n• Breast tenderness"
                else:
                    response = "I need your last period date to calculate ovulation. Say 'My period started [date]'."
            else:
                response = "I need your period history to calculate ovulation. Please log your last period first."
        
        elif intent == 'cycle_info':
            if user_data and user_data[2]:
                cycle_length = user_data[2]
                response = f"Your current cycle length is set to **{cycle_length} days**.\n\n"
                response += "**Normal cycle ranges:** 21-35 days\n"
                response += "**Average cycle:** 28 days\n\n"
                response += "To update your cycle length, say: 'My cycle is X days'"
            else:
                response = "I don't have your cycle information yet. The default is 28 days.\n\n"
                response += "You can update it by saying: 'My cycle is 30 days' or similar."
        
        elif intent == 'set_reminder':
            response = "I can remind you about:\n\n"
            response += "1. **Period start** - 2 days before expected date\n"
            response += "2. **Ovulation** - When you're most fertile\n"
            response += "3. **Pill/Medication** - Daily reminders\n"
            response += "4. **Symptom check-ins** - How you're feeling\n\n"
            response += "What would you like me to remind you about?"
            actions = ["Period start", "Ovulation", "Medication", "Symptoms"]
        
        else:
            # Default/unknown intent
            response = "I'm here to help with period tracking and menstrual health! I can:\n\n"
            response += "• Log your period start/end dates\n"
            response += "• Predict your next period\n"
            response += "• Track symptoms and suggest relief\n"
            response += "• Calculate ovulation dates\n"
            response += "• Answer questions about PMS, pain relief, etc.\n\n"
            response += "Try saying:\n'My period started today'\n'When is my next period?'\n'I have cramps'\n'What helps with period pain?'"
        
        # Save chat history
        c.execute('''
            INSERT INTO chat_history (user_id, user_message, bot_response, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user_id, message, response, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        return {
            "response": response,
            "intent": intent,
            "actions": actions,
            "timestamp": datetime.now().isoformat()
        }

# Initialize chatbot
chatbot = PeriodTrackerChatbot()

# API Routes
@app.route('/')
def home():
    return jsonify({
        "message": "Period Tracker Chatbot API",
        "status": "running",
        "endpoints": {
            "/chat": "POST - Send message to chatbot",
            "/user/<user_id>": "GET - Get user data",
            "/symptoms/<user_id>": "GET - Get user symptoms",
            "/history/<user_id>": "GET - Get chat history"
        }
    })

@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    try:
        data = request.json
        
        if not data or 'message' not in data or 'user_id' not in data:
            return jsonify({
                "error": "Missing message or user_id",
                "status": "error"
            }), 400
        
        message = data['message']
        user_id = data['user_id']
        
        # Process message
        result = chatbot.process_message(message, user_id)
        
        return jsonify({
            "status": "success",
            "data": result
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/user/<user_id>', methods=['GET'])
def get_user_data(user_id):
    """Get user data"""
    try:
        conn = sqlite3.connect('period_tracker.db')
        c = conn.cursor()
        
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_data = c.fetchone()
        
        c.execute("SELECT * FROM symptoms WHERE user_id = ? ORDER BY date DESC LIMIT 10", (user_id,))
        symptoms = c.fetchall()
        
        conn.close()
        
        if user_data:
            user_dict = {
                "user_id": user_data[0],
                "last_period_date": user_data[1],
                "cycle_length": user_data[2],
                "period_duration": user_data[3],
                "created_at": user_data[4]
            }
            
            # Calculate predictions
            if user_data[1]:
                next_period = chatbot.calculate_next_period(user_data[1], user_data[2] or 28)
                ovulation = chatbot.calculate_ovulation(user_data[1], user_data[2] or 28)
            else:
                next_period = None
                ovulation = None
            
            return jsonify({
                "status": "success",
                "user": user_dict,
                "predictions": {
                    "next_period": next_period,
                    "ovulation_date": ovulation
                },
                "recent_symptoms": symptoms
            })
        else:
            return jsonify({
                "status": "success",
                "user": None,
                "message": "User not found"
            })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/symptoms/<user_id>', methods=['POST'])
def log_symptom(user_id):
    """Log a symptom"""
    try:
        data = request.json
        
        if not data or 'symptom' not in data:
            return jsonify({"error": "Missing symptom data"}), 400
        
        symptom = data['symptom']
        severity = data.get('severity', 'moderate')
        notes = data.get('notes', '')
        
        conn = sqlite3.connect('period_tracker.db')
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO symptoms (user_id, symptom, severity, date, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, symptom, severity, datetime.now().strftime('%Y-%m-%d'), notes))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": f"Symptom '{symptom}' logged successfully"
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/history/<user_id>', methods=['GET'])
def get_chat_history(user_id):
    """Get chat history for user"""
    try:
        limit = request.args.get('limit', 50)
        
        conn = sqlite3.connect('period_tracker.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT user_message, bot_response, timestamp 
            FROM chat_history 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (user_id, limit))
        
        history = c.fetchall()
        conn.close()
        
        formatted_history = []
        for msg in history:
            formatted_history.append({
                "user_message": msg[0],
                "bot_response": msg[1],
                "timestamp": msg[2]
            })
        
        return jsonify({
            "status": "success",
            "history": formatted_history
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/update_cycle', methods=['POST'])
def update_cycle():
    """Update user's cycle length"""
    try:
        data = request.json
        
        if not data or 'user_id' not in data or 'cycle_length' not in data:
            return jsonify({"error": "Missing user_id or cycle_length"}), 400
        
        user_id = data['user_id']
        cycle_length = int(data['cycle_length'])
        
        if not 21 <= cycle_length <= 45:
            return jsonify({"error": "Cycle length should be between 21-45 days"}), 400
        
        conn = sqlite3.connect('period_tracker.db')
        c = conn.cursor()
        
        # Check if user exists
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone():
            c.execute('''
                UPDATE users SET cycle_length = ? WHERE user_id = ?
            ''', (cycle_length, user_id))
        else:
            c.execute('''
                INSERT INTO users (user_id, cycle_length, created_at)
                VALUES (?, ?, ?)
            ''', (user_id, cycle_length, datetime.now().strftime('%Y-%m-%d')))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": f"Cycle length updated to {cycle_length} days"
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))  # Use PORT if set, otherwise default to 5000
    # Disable debug in production
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)