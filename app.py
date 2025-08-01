from flask import Flask, render_template, request, jsonify
import requests
import os
from datetime import datetime, timedelta
import anthropic
from deep_translator import GoogleTranslator
from dotenv import load_dotenv
import tempfile
import base64
import speech_recognition as sr
from gtts import gTTS

load_dotenv()

app = Flask(__name__)

CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')

if CLAUDE_API_KEY:
    claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
else:
    claude_client = None
    print("Warning: CLAUDE_API_KEY not set. Chat functionality will be limited.")

# Speech recognition setup
recognizer = sr.Recognizer()

# Gujarat districts only
GUJARAT_DISTRICTS = {
    "Ahmedabad": {"lat": 23.0225, "lon": 72.5714},
    "Amreli": {"lat": 21.6009, "lon": 71.2148},
    "Anand": {"lat": 22.5645, "lon": 72.9289},
    "Aravalli": {"lat": 23.2538, "lon": 73.0301},
    "Banaskantha": {"lat": 24.1719, "lon": 72.4383},
    "Bharuch": {"lat": 21.7051, "lon": 72.9959},
    "Bhavnagar": {"lat": 21.7645, "lon": 72.1519},
    "Botad": {"lat": 22.1693, "lon": 71.6669},
    "Chhota Udaipur": {"lat": 22.3048, "lon": 74.0130},
    "Dahod": {"lat": 22.8382, "lon": 74.2592},
    "Dang": {"lat": 20.7331, "lon": 73.7056},
    "Devbhoomi Dwarka": {"lat": 22.2394, "lon": 68.9678},
    "Gandhinagar": {"lat": 23.2156, "lon": 72.6369},
    "Gir Somnath": {"lat": 20.8955, "lon": 70.4008},
    "Jamnagar": {"lat": 22.4707, "lon": 70.0577},
    "Junagadh": {"lat": 21.5222, "lon": 70.4579},
    "Kheda": {"lat": 22.7507, "lon": 72.6947},
    "Kutch": {"lat": 23.7337, "lon": 69.8597},
    "Mahisagar": {"lat": 23.0644, "lon": 73.6508},
    "Mehsana": {"lat": 23.5958, "lon": 72.3693},
    "Morbi": {"lat": 22.8173, "lon": 70.8378},
    "Narmada": {"lat": 21.9045, "lon": 73.5004},
    "Navsari": {"lat": 20.9467, "lon": 72.9520},
    "Panchmahal": {"lat": 22.8556, "lon": 73.4285},
    "Patan": {"lat": 23.8502, "lon": 72.1262},
    "Porbandar": {"lat": 21.6417, "lon": 69.6293},
    "Rajkot": {"lat": 22.3039, "lon": 70.8022},
    "Sabarkantha": {"lat": 23.9441, "lon": 72.9814},
    "Surat": {"lat": 21.1702, "lon": 72.8311},
    "Surendranagar": {"lat": 22.7196, "lon": 71.6369},
    "Tapi": {"lat": 21.1307, "lon": 73.3733},
    "Vadodara": {"lat": 22.3072, "lon": 73.1812},
    "Valsad": {"lat": 20.5992, "lon": 72.9342}
}

SUPPORTED_LANGUAGES = {
    'en': {'name': 'English', 'sr_lang': 'en-IN', 'tts_lang': 'en'},
    'hi': {'name': 'Hindi', 'sr_lang': 'hi-IN', 'tts_lang': 'hi'},
    'gu': {'name': 'Gujarati', 'sr_lang': 'gu-IN', 'tts_lang': 'gu'}
}

@app.route('/')
def index():
    return render_template('voice_assistant.html',
                         districts=GUJARAT_DISTRICTS.keys())

# Main text processing route
@app.route('/process_text', methods=['POST'])
def process_text():
    data = request.json
    text = data.get('text', '').lower()
    language = data.get('language', 'en')
    
    # Check if text is about weather
    if any(word in text for word in ['weather', 'temperature', 'rain', 'forecast', 'climate']):
        location_info = extract_location_from_command(text)
        if location_info:
            district = location_info['district']
            coords = GUJARAT_DISTRICTS[district]
            weather_data = get_weather_data(coords['lat'], coords['lon'])
            if weather_data:
                response = format_weather_response(weather_data, district)
            else:
                response = "Sorry, I couldn't fetch weather data at the moment."
        else:
            response = "Please specify a Gujarat district for weather information."
    
    # Check if text is about commodity prices
    elif any(word in text for word in ['price', 'commodity', 'market', 'cost', 'rate']):
        district = None
        for d in GUJARAT_DISTRICTS:
            if d.lower() in text:
                district = d
                break
        
        date_str = None  # Could implement date extraction here
        
        return get_commodity_prices_internal(district, date_str, language)
    
    # Otherwise, general chat
    else:
        response = get_claude_response(text)
    
    # Translate response if needed
    if language != 'en':
        try:
            response = translate_text(response, language)
        except Exception as e:
            print(f"Translation failed: {e}")
    
    return jsonify({
        'response': response,
        'districts': list(GUJARAT_DISTRICTS.keys())
    })

# Speech Recognition Route
@app.route('/speech_to_text', methods=['POST'])
def speech_to_text():
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        language = request.json.get('language', 'en') if request.is_json else request.form.get('language', 'en')
        
        # Save uploaded audio to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            audio_file.save(tmp_file.name)
            
            # Use speech recognition
            with sr.AudioFile(tmp_file.name) as source:
                audio_data = recognizer.record(source)
                
            sr_language = SUPPORTED_LANGUAGES.get(language, {}).get('sr_lang', 'en-IN')
            text = recognizer.recognize_google(audio_data, language=sr_language)
            
            # Clean up temp file
            os.unlink(tmp_file.name)
            
            return jsonify({'text': text})
            
    except sr.UnknownValueError:
        return jsonify({'error': 'Could not understand audio'}), 400
    except sr.RequestError as e:
        return jsonify({'error': f'Speech recognition service error: {e}'}), 500
    except Exception as e:
        return jsonify({'error': f'Error processing audio: {e}'}), 500

# Text to Speech Route
@app.route('/text_to_speech', methods=['POST'])
def text_to_speech():
    try:
        data = request.json
        text = data.get('text', '')
        language = data.get('language', 'en')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Get the language code for gTTS
        tts_lang = SUPPORTED_LANGUAGES.get(language, {}).get('tts_lang', 'en')
        
        # Create gTTS object
        tts = gTTS(text=text, lang=tts_lang, slow=False)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
            tts.save(tmp_file.name)
            
            # Read the generated audio file
            with open(tmp_file.name, 'rb') as audio_file:
                audio_data = audio_file.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Clean up temp file
            os.unlink(tmp_file.name)
            
            return jsonify({'audio': audio_base64, 'format': 'mp3'})
            
    except Exception as e:
        return jsonify({'error': f'Error generating speech: {e}'}), 500

# Weather Routes
@app.route('/get_weather', methods=['POST'])
def get_weather():
    data = request.json
    district = data.get('district')
    language = data.get('language', 'en')
    
    if not district:
        return jsonify({'error': 'Please provide district name'}), 400
    
    location = GUJARAT_DISTRICTS.get(district)
    if not location:
        return jsonify({'error': 'District not found in Gujarat'}), 404
    
    weather_data = get_weather_data(location['lat'], location['lon'])
    
    if not weather_data:
        return jsonify({'error': 'Failed to fetch weather data'}), 500
    
    response = format_weather_response(weather_data, district)
    
    if language != 'en':
        try:
            response = translate_text(response, language)
        except Exception as e:
            print(f"Translation failed: {e}")
    
    return jsonify({'response': response})

def get_commodity_prices_internal(district, date_str, language):
    base_url = "https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24"
    params = {
        "api-key": "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b",
        "format": "json",
        "filters[State]": "Gujarat",
        "limit": "100"
    }
    
    if district:
        params["filters[District]"] = district
    
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d/%m/%Y')
            params["filters[Arrival_Date]"] = formatted_date
        except ValueError:
            pass
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        api_data = response.json()
        records = api_data.get('records', [])
        
        if not records:
            response_text = "No commodity price data found for the selected criteria."
        else:
            response_text = format_commodity_response(records, district, date_str)
        
        if language != 'en':
            try:
                response_text = translate_text(response_text, language)
            except Exception as e:
                print(f"Translation failed: {e}")
        
        return jsonify({'response': response_text, 'records': records})
        
    except Exception as e:
        return jsonify({'error': f'Error fetching commodity data: {e}'}), 500

@app.route('/get_commodity_prices', methods=['POST'])
def get_commodity_prices():
    data = request.json
    district = data.get('district', '')
    date_str = data.get('date', '')
    language = data.get('language', 'en')
    
    return get_commodity_prices_internal(district, date_str, language)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message')
    language = data.get('language', 'en')
    context = data.get('context', '')
    
    if language != 'en':
        message = translate_text(message, 'en')
    
    response = get_claude_response(message, context)
    
    if language != 'en':
        response = translate_text(response, language)
    
    return jsonify({'response': response})

# Voice Command Processing Route
@app.route('/process_voice_command', methods=['POST'])
def process_voice_command():
    data = request.json
    command = data.get('command', '').lower()
    language = data.get('language', 'en')
    
    # Analyze the command to determine intent
    if any(word in command for word in ['weather', 'temperature', 'rain', 'forecast']):
        # Extract location from command
        location_info = extract_location_from_command(command)
        if location_info:
            district = location_info['district']
            coords = GUJARAT_DISTRICTS[district]
            weather_data = get_weather_data(coords['lat'], coords['lon'])
            if weather_data:
                response = format_weather_response(weather_data, district)
            else:
                response = "Sorry, I couldn't fetch weather data at the moment."
        else:
            response = "Please specify a Gujarat district for weather information."
    
    elif any(word in command for word in ['price', 'commodity', 'market', 'cost']):
        # Extract commodity/location info
        district = extract_commodity_info_from_command(command)
        if district:
            return get_commodity_prices_internal(district, None, language)
        else:
            response = "Please specify a Gujarat district for commodity prices."
    
    else:
        # General chat
        response = get_claude_response(command, "")
    
    if language != 'en':
        response = translate_text(response, language)
    
    return jsonify({'response': response})

# Helper Functions
def get_weather_data(lat, lon):
    """Fetch weather data from Open-Meteo API"""
    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': lat,
        'longitude': lon,
        'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max',
        'timezone': 'Asia/Kolkata',
        'forecast_days': 7
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("Weather API request timed out")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error in weather API: {e}")
        return None

def format_weather_response(data, district):
    """Format weather data into readable response"""
    if not data:
        return "Sorry, couldn't fetch weather data."
    
    current = data.get('current', {})
    daily = data.get('daily', {})
    
    response = f"Weather in {district}, Gujarat:\n"
    response += f"Temperature: {current.get('temperature_2m', 'N/A')}°C\n"
    response += f"Feels like: {current.get('apparent_temperature', 'N/A')}°C\n"
    response += f"Humidity: {current.get('relative_humidity_2m', 'N/A')}%\n"
    response += f"Wind Speed: {current.get('wind_speed_10m', 'N/A')} km/h\n"
    
    if daily.get('temperature_2m_max') and daily.get('temperature_2m_min'):
        response += f"Today's Range: {daily['temperature_2m_min'][0]}°C - {daily['temperature_2m_max'][0]}°C\n"
    
    return response

def format_commodity_response(records, district, date):
    """Format commodity data into readable response"""
    if not records:
        return "No commodity price data found."
    
    response = f"Commodity prices"
    if district:
        response += f" in {district}, Gujarat"
    if date:
        response += f" for {date}"
    response += ":\n\n"
    
    for i, record in enumerate(records[:5]):  # Limit to first 5 records
        response += f"{i+1}. {record.get('Commodity', 'N/A')} ({record.get('Variety', 'N/A')})\n"
        response += f"   Market: {record.get('Market', 'N/A')}\n"
        response += f"   Price Range: ₹{record.get('Min_Price', 'N/A')} - ₹{record.get('Max_Price', 'N/A')}\n"
        response += f"   Modal Price: ₹{record.get('Modal_Price', 'N/A')}\n\n"
    
    if len(records) > 5:
        response += f"... and {len(records) - 5} more items.\n"
    
    return response

def get_claude_response(message, context=""):
    """Get response from Claude API"""
    if not claude_client:
        return "Chat service is not available."
    
    try:
        system_prompt = """You are a helpful assistant for Gujarat, India users. You can help with weather information, 
        commodity prices, and general questions about Gujarat. Be friendly and provide concise, helpful responses."""
        
        full_context = f"{context}\n\nUser: {message}" if context else message
        
        response = claude_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            temperature=0.7,
            system=system_prompt,
            messages=[{"role": "user", "content": full_context}]
        )
        
        return response.content[0].text
    except Exception as e:
        print(f"Error with Claude API: {e}")
        return "Sorry, I'm having trouble processing your request."

def translate_text(text, target_language):
    """Translate text using GoogleTranslator"""
    try:
        if target_language == 'en':
            return text
        
        language_map = {
            'hi': 'hindi',
            'gu': 'gujarati'
        }
        
        target_lang = language_map.get(target_language, target_language)
        translator = GoogleTranslator(source='english', target=target_lang)
        
        return translator.translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def extract_location_from_command(command):
    """Extract location information from voice command"""
    for district in GUJARAT_DISTRICTS:
        if district.lower() in command.lower():
            return {
                'district': district
            }
    return None

def extract_commodity_info_from_command(command):
    """Extract district from commodity command"""
    for district in GUJARAT_DISTRICTS:
        if district.lower() in command.lower():
            return district
    return None

if __name__ == '__main__':
    print("🚀 Starting Gujarat Text Assistant...")
    print("Features: Weather + Commodity Prices + Chat for Gujarat")
    print("Supported Languages: English, Hindi, Gujarati")
    print("Access at: http://localhost:5000\n")
    
    app.run(debug=True, port=5000)