from flask import Flask, render_template, request, jsonify
import requests
import os
from datetime import datetime
import anthropic
from deep_translator import GoogleTranslator
from dotenv import load_dotenv
import tempfile
import base64
import speech_recognition as sr
from gtts import gTTS
from flask_cors import CORS
import traceback

load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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

# Helper function for standardized API responses
def create_response(message, data=None, status=200, error=None):
    """Create a standardized API response format"""
    response_data = {
        "message": message,
        "data": data if data is not None else {},
        "status": status
    }
    
    if error:
        response_data["data"] = {"error": error}
    
    return jsonify(response_data), status

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

def get_commodity_prices_internal(district, date_str, language):
    """Internal function to handle commodity prices logic"""
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
            return create_response(
                "No commodity price data found", 
                data={"response": "No commodity price data found for the selected criteria.", "records": []}, 
                status=200
            )
        else:
            response_text = format_commodity_response(records, district, date_str)
        
        if language != 'en':
            try:
                response_text = translate_text(response_text, language)
            except Exception as e:
                print(f"Translation failed: {e}")
        
        return create_response(
            "Commodity prices retrieved successfully", 
            data={"response": response_text, "records": records}, 
            status=200
        )
        
    except Exception as e:
        return create_response(
            "Failed to retrieve commodity prices", 
            error=f"Error fetching commodity data: {e}", 
            status=500
        )

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

# Main Routes
@app.route('/')
def index():
    return render_template('voice.html', districts=GUJARAT_DISTRICTS.keys())

# API Endpoints
@app.route('/process_text', methods=['POST'])
def process_text():
    data = request.json
    text = data.get('text', '').lower()
    language = data.get('language', 'en')
    
    if not text:
        return create_response("Failed to process text", error="No text provided", status=400)
    
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
                return create_response("Failed to process text", error="Couldn't fetch weather data", status=500)
        else:
            return create_response("Failed to process text", error="Please specify a Gujarat district for weather information", status=400)
    
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
    
    return create_response("Text processed successfully", data={"response": response}, status=200)

@app.route('/get_weather', methods=['POST'])
def get_weather():
    data = request.json
    district = data.get('district')
    language = data.get('language', 'en')
    
    if not district:
        return create_response("Failed to retrieve weather data", error="Please provide district name", status=400)
    
    location = GUJARAT_DISTRICTS.get(district)
    if not location:
        return create_response("Failed to retrieve weather data", error="District not found in Gujarat", status=404)
    
    weather_data = get_weather_data(location['lat'], location['lon'])
    
    if not weather_data:
        return create_response("Failed to retrieve weather data", error="Failed to fetch weather data", status=500)
    
    response = format_weather_response(weather_data, district)
    
    if language != 'en':
        try:
            response = translate_text(response, language)
        except Exception as e:
            print(f"Translation failed: {e}")
    
    return create_response("Weather data retrieved successfully", data={"response": response}, status=200)

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
    
    if not message:
        return create_response("Failed to generate chat response", error="No message provided", status=400)
    
    if language != 'en':
        message = translate_text(message, 'en')
    
    response = get_claude_response(message, context)
    
    if not response:
        return create_response("Failed to generate chat response", error="Unable to generate response", status=500)
    
    if language != 'en':
        response = translate_text(response, language)
    
    return create_response("Chat response generated successfully", data={"response": response}, status=200)

@app.route('/speech_to_text', methods=['POST'])
def speech_to_text():
    tmp_file_path = None
    try:
        print("Speech to text endpoint called")
        
        if 'audio' not in request.files:
            print("No audio file in request")
            return create_response("Failed to convert speech to text", error="No audio file provided", status=400)
        
        audio_file = request.files['audio']
        print(f"Audio file received: {audio_file.filename if audio_file.filename else 'No filename'}")
        
        # Get language from form data only
        language = request.form.get('language', 'en')
        print(f"Language: {language}")
        
        # Save uploaded audio to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_file_path = tmp_file.name
            audio_file.save(tmp_file_path)
            print(f"Audio saved to temporary file: {tmp_file_path}")
            
            try:
                # Use speech recognition
                with sr.AudioFile(tmp_file_path) as source:
                    print("Reading audio file")
                    audio_data = recognizer.record(source)
                    
                sr_language = SUPPORTED_LANGUAGES.get(language, {}).get('sr_lang', 'en-IN')
                print(f"Recognizing with language: {sr_language}")
                text = recognizer.recognize_google(audio_data, language=sr_language)
                print(f"Recognized text: {text}")
                
                return create_response(
                    "Speech converted to text successfully", 
                    data={"text": text}, 
                    status=200
                )
            except sr.UnknownValueError as e:
                print(f"Could not understand audio: {e}")
                return create_response("Failed to convert speech to text", error="Could not understand audio", status=400)
            except sr.RequestError as e:
                print(f"Speech recognition service error: {e}")
                return create_response("Failed to convert speech to text", error=f"Speech recognition service error: {e}", status=500)
            except Exception as e:
                print(f"Error processing audio: {e}")
                traceback.print_exc()
                return create_response("Failed to convert speech to text", error=f"Error processing audio: {e}", status=500)
                
    except Exception as e:
        print(f"Speech to text error: {e}")
        traceback.print_exc()
        return create_response("Failed to convert speech to text", error=f"Error: {str(e)}", status=500)
    finally:
        # Clean up temp file
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
                print(f"Temporary file removed: {tmp_file_path}")
            except Exception as e:
                print(f"Error removing temporary file: {e}")

@app.route('/text_to_speech', methods=['POST'])
def text_to_speech():
    tmp_file_path = None
    try:
        data = request.json
        text = data.get('text', '')
        language = data.get('language', 'en')
        
        if not text:
            return create_response("Failed to convert text to speech", error="No text provided", status=400)
        
        # Get the language code for gTTS
        tts_lang = SUPPORTED_LANGUAGES.get(language, {}).get('tts_lang', 'en')
        
        # Create gTTS object
        tts = gTTS(text=text, lang=tts_lang, slow=False)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
            tmp_file_path = tmp_file.name
            tts.save(tmp_file_path)
            
            # Read the generated audio file
            with open(tmp_file_path, 'rb') as audio_file:
                audio_data = audio_file.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            return create_response(
                "Text converted to speech successfully", 
                data={"audio": audio_base64, "format": "mp3"}, 
                status=200
            )
            
    except Exception as e:
        print(f"Text to speech error: {e}")
        traceback.print_exc()
        return create_response("Failed to convert text to speech", error=f"Error generating speech: {e}", status=500)
    finally:
        # Clean up temp file
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
            except Exception as e:
                print(f"Error removing temporary file: {e}")

@app.route('/process_voice_command', methods=['POST'])
def process_voice_command():
    data = request.json
    command = data.get('command', '').lower()
    language = data.get('language', 'en')
    
    if not command:
        return create_response("Failed to process voice command", error="No command provided", status=400)
    
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
                return create_response("Failed to process voice command", error="Couldn't fetch weather data", status=500)
        else:
            return create_response("Failed to process voice command", error="Please specify a Gujarat district for weather information", status=400)
    
    elif any(word in command for word in ['price', 'commodity', 'market', 'cost']):
        # Extract commodity/location info
        district = extract_commodity_info_from_command(command)
        if district:
            return get_commodity_prices_internal(district, None, language)
        else:
            return create_response("Failed to process voice command", error="Please specify a Gujarat district for commodity prices", status=400)
    
    else:
        # General chat
        response = get_claude_response(command, "")
    
    if language != 'en':
        response = translate_text(response, language)
    
    return create_response("Voice command processed successfully", data={"response": response}, status=200)

# Voice-specific endpoints
@app.route('/voice_interaction', methods=['POST'])
def voice_interaction():
    """Combined endpoint that handles both speech-to-text and text-to-speech"""
    tmp_file_path = None
    try:
        print("Voice interaction endpoint called")
        
        if 'audio' not in request.files:
            print("No audio file in request")
            return create_response("Failed to process voice interaction", error="No audio file provided", status=400)
        
        audio_file = request.files['audio']
        print(f"Audio file received: {audio_file.filename if audio_file.filename else 'No filename'}")
        
        # Get language from form data only
        language = request.form.get('language', 'en')
        print(f"Language: {language}")
        
        # 1. Speech to Text
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_file_path = tmp_file.name
            audio_file.save(tmp_file_path)
            print(f"Audio saved to temporary file: {tmp_file_path}")
            
            try:
                with sr.AudioFile(tmp_file_path) as source:
                    print("Reading audio file")
                    audio_data = recognizer.record(source)
                    
                sr_language = SUPPORTED_LANGUAGES.get(language, {}).get('sr_lang', 'en-IN')
                print(f"Recognizing with language: {sr_language}")
                text = recognizer.recognize_google(audio_data, language=sr_language)
                print(f"Recognized text: {text}")
            except sr.UnknownValueError as e:
                print(f"Could not understand audio: {e}")
                return create_response("Failed to process voice interaction", error="Could not understand audio", status=400)
            except sr.RequestError as e:
                print(f"Speech recognition service error: {e}")
                return create_response("Failed to process voice interaction", error=f"Speech recognition service error: {e}", status=500)
            except Exception as e:
                print(f"Speech recognition error: {e}")
                traceback.print_exc()
                return create_response("Failed to process voice interaction", error=f"Speech recognition error: {e}", status=500)
        
        # 2. Process the text
        print(f"Processing recognized text: {text}")
        # Check if text is about weather
        if any(word in text.lower() for word in ['weather', 'temperature', 'rain', 'forecast', 'climate']):
            location_info = extract_location_from_command(text)
            if location_info:
                district = location_info['district']
                coords = GUJARAT_DISTRICTS[district]
                weather_data = get_weather_data(coords['lat'], coords['lon'])
                if weather_data:
                    response_text = format_weather_response(weather_data, district)
                else:
                    return create_response("Failed to process voice interaction", error="Couldn't fetch weather data", status=500)
            else:
                response_text = "Please specify a Gujarat district for weather information."
        
        # Check if text is about commodity prices
        elif any(word in text.lower() for word in ['price', 'commodity', 'market', 'cost', 'rate']):
            district = None
            for d in GUJARAT_DISTRICTS:
                if d.lower() in text.lower():
                    district = d
                    break
            
            if district:
                try:
                    commodity_response, status_code = get_commodity_prices_internal(district, None, 'en')
                    if status_code == 200:
                        commodity_data = commodity_response.json
                        response_text = commodity_data.get('data', {}).get('response', "No commodity price data found.")
                    else:
                        response_text = "Error retrieving commodity prices."
                except Exception as e:
                    print(f"Error getting commodity prices: {e}")
                    response_text = "Error retrieving commodity prices."
            else:
                response_text = "Please specify a Gujarat district for commodity prices."
        
        # Otherwise, general chat
        else:
            response_text = get_claude_response(text)
        
        # 3. Translate response if needed (to match input language)
        print(f"Response text before translation: {response_text}")
        if language != 'en':
            try:
                response_text = translate_text(response_text, language)
                print(f"Translated response: {response_text}")
            except Exception as e:
                print(f"Translation failed: {e}")
        
        # 4. Convert response to speech
        print(f"Converting to speech in language: {language}")
        tts_lang = SUPPORTED_LANGUAGES.get(language, {}).get('tts_lang', 'en')
        
        tts_tmp_file = None
        try:
            tts = gTTS(text=response_text, lang=tts_lang, slow=False)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                tts_tmp_file = tmp_file.name
                tts.save(tts_tmp_file)
                
                with open(tts_tmp_file, 'rb') as audio_file:
                    audio_data = audio_file.read()
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        except Exception as e:
            print(f"TTS error: {e}")
            traceback.print_exc()
            audio_base64 = None
        finally:
            if tts_tmp_file and os.path.exists(tts_tmp_file):
                try:
                    os.unlink(tts_tmp_file)
                except Exception as e:
                    print(f"Error removing TTS temporary file: {e}")
        
        # 5. Return both the text and speech
        print("Sending voice interaction response")
        return create_response(
            "Voice interaction processed successfully", 
            data={
                "recognized_text": text,
                "response_text": response_text,
                "audio": audio_base64,
                "format": "mp3"
            }, 
            status=200
        )
            
    except Exception as e:
        print(f"Voice interaction error: {e}")
        traceback.print_exc()
        return create_response("Failed to process voice interaction", error=f"Error: {str(e)}", status=500)
    finally:
        # Clean up temporary file
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
                print(f"Temporary file removed: {tmp_file_path}")
            except Exception as e:
                print(f"Error removing temporary file: {e}")

# Add a health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return create_response("Service is healthy", data={"status": "UP"}, status=200)

@app.route('/', methods=['GET'])
def root():
    return create_response(
        "Gujarat Text Assistant API", 
        data={
            "name": "Gujarat Text Assistant API",
            "version": "1.0.0",
            "endpoints": [
                "/health",
                "/process_text",
                "/get_weather",
                "/get_commodity_prices",
                "/chat",
                "/speech_to_text",
                "/text_to_speech",
                "/process_voice_command",
                "/voice_interaction"
            ]
        }, 
        status=200
    )

if __name__ == '__main__':
    print("🚀 Starting Gujarat Voice Assistant API...")
    print("Supported Languages: English, Hindi, Gujarati")
    print("Access at: http://localhost:5000\n")
    
    app.run(host='0.0.0.0', debug=True, port=5000)