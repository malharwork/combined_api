from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import io
import boto3
from datetime import datetime, timedelta
import anthropic
from deep_translator import GoogleTranslator
from dotenv import load_dotenv
import base64
from flask_cors import CORS
from PIL import Image
from difflib import SequenceMatcher
import socket

load_dotenv()

app = Flask(__name__)
CORS(app)  

CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
MODEL_ARN = os.getenv("MODEL_ARN")

if CLAUDE_API_KEY:
   claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
else:
   claude_client = None
   print("Warning: CLAUDE_API_KEY not set. Chat functionality will be limited.")

if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and MODEL_ARN:
   rekognition = boto3.client('rekognition',
       region_name='ap-south-1',
       aws_access_key_id=AWS_ACCESS_KEY_ID,
       aws_secret_access_key=AWS_SECRET_ACCESS_KEY
   )
else:
   rekognition = None
   print("Warning: AWS credentials or MODEL_ARN not set. Disease detection functionality will be limited.")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 4_000_000
MAX_IMAGE_DIMENSION = 4096

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

# Enhanced district name mappings for better pronunciation recognition
DISTRICT_NAME_VARIATIONS = {
    # English variations and common pronunciations
    "ahmedabad": "Ahmedabad",
    "amdavad": "Ahmedabad",
    "ahmadabad": "Ahmedabad",
    "surat": "Surat",
    "vadodara": "Vadodara",
    "baroda": "Vadodara",
    "rajkot": "Rajkot",
    "rajkot": "Rajkot",
    "rajcot": "Rajkot",
    "gandhinagar": "Gandhinagar",
    "jamnagar": "Jamnagar",
    "bhavnagar": "Bhavnagar",
    "junagadh": "Junagadh",
    "mehsana": "Mehsana",
    "mehsana": "Mehsana",
    "patan": "Patan",
    "kutch": "Kutch",
    "kachchh": "Kutch",
    "kuch": "Kutch",
    "anand": "Anand",
    "kheda": "Kheda",
    "bharuch": "Bharuch",
    "narmada": "Narmada",
    "dahod": "Dahod",
    "panchmahal": "Panchmahal",
    "sabarkantha": "Sabarkantha",
    "banaskantha": "Banaskantha",
    "amreli": "Amreli",
    "porbandar": "Porbandar",
    "surendranagar": "Surendranagar",
    "morbi": "Morbi",
    "botad": "Botad",
    "gir somnath": "Gir Somnath",
    "devbhoomi dwarka": "Devbhoomi Dwarka",
    "navsari": "Navsari",
    "valsad": "Valsad",
    "tapi": "Tapi",
    "dang": "Dang",
    "aravalli": "Aravalli",
    "mahisagar": "Mahisagar",
    "chhota udaipur": "Chhota Udaipur",
    
    # Gujarati district names
    "અમદાવાદ": "Ahmedabad",
    "સુરત": "Surat",
    "વડોદરા": "Vadodara",
    "રાજકોટ": "Rajkot",
    "ગાંધીનગર": "Gandhinagar",
    "જામનગર": "Jamnagar",
    "ભાવનગર": "Bhavnagar",
    "જૂનાગઢ": "Junagadh",
    "મહેસાણા": "Mehsana",
    "પાટણ": "Patan",
    "કચ્છ": "Kutch",
    "આણંદ": "Anand",
    "ખેડા": "Kheda",
    "ભરૂચ": "Bharuch",
    "નર્મદા": "Narmada",
    "દાહોદ": "Dahod",
    "પંચમહાલ": "Panchmahal",
    "સાબરકાંઠા": "Sabarkantha",
    "બનાસકાંઠા": "Banaskantha",
    "અમરેલી": "Amreli",
    "પોરબંદર": "Porbandar",
    "સુરેન્દ્રનગર": "Surendranagar",
    "મોરબી": "Morbi",
    "બોટાદ": "Botad",
    "ગીર સોમનાથ": "Gir Somnath",
    "દેવભૂમિ દ્વારકા": "Devbhoomi Dwarka",
    "નવસારી": "Navsari",
    "વલસાડ": "Valsad",
    "તાપી": "Tapi",
    "દાંગ": "Dang",
    "અરાવલી": "Aravalli",
    "મહિસાગર": "Mahisagar",
    "છોટા ઉદયપુર": "Chhota Udaipur",
    
    # Hindi district names
    "अहमदाबाद": "Ahmedabad",
    "सूरत": "Surat",
    "वडोदरा": "Vadodara",
    "राजकोट": "Rajkot",
    "गांधीनगर": "Gandhinagar",
    "जामनगर": "Jamnagar",
    "भावनगर": "Bhavnagar",
    "जूनागढ": "Junagadh",
    "मेहसाना": "Mehsana",
    "पाटण": "Patan",
    "कच्छ": "Kutch",
    "आणंद": "Anand",
    "खेडा": "Kheda",
    "भरूच": "Bharuch",
    "नर्मदा": "Narmada",
    "दाहोद": "Dahod",
    "पंचमहाल": "Panchmahal",
    "साबरकांठा": "Sabarkantha",
    "बनासकांठा": "Banaskantha",
    "अमरेली": "Amreli",
    "पोरबंदर": "Porbandar",
    "सुरेंद्रनगर": "Surendranagar",
    "मोरबी": "Morbi",
    "बोटाद": "Botad"
}

DISEASE_MESSAGES = {
   "unsupported_format": {
       "en": "Unsupported file format. Please upload a JPG or PNG image.",
       "hi": "असमर्थित फ़ाइल प्रारूप। कृपया JPG या PNG फोटो अपलोड करें।",
       "gu": "અસમર્થિત ફાઇલ ફોર્મેટ. કૃપા કરીને JPG અથવા PNG છબી અપલોડ કરો."
   },
   "no_disease": {
       "en": "No disease detected. Please upload a clearer vegetable image.",
       "hi": "कोई बीमारी नहीं पाई गई। कृपया एक स्पष्ट सब्ज़ी की छवि अपलोड करें।",
       "gu": "કોઈ રોગ મળ્યો નથી. કૃપા કરીને વધુ સ્પષ્ટ શાકભાજીની છબી અપલોડ કરો."
   },
   "success": {
       "en": "Disease(s) classified successfully",
       "hi": "बीमारी(यों) को सफलतापूर्वक वर्गीकृत किया गया",
       "gu": "રોગ(ઓ)ની સફળતાપૂર્વક વર્ગીકરણ થયું છે",
   },
   "invalid_image": {
       "en": "Model is not running or image processing failed",
       "hi": "मॉडल नहीं चल रहा है या छवि प्रसंस्करण विफल हुआ",
       "gu": "મોડેલ ચાલી રહ્યું નથી અથવા છબી પ્રક્રિયા નિષ્ફળ થઈ",
   }
}

DISTRICT_ERROR_MESSAGES = {
    "district_not_found": {
        "en": "I couldn't find that district. Please check the spelling or try one of these Gujarat districts:",
        "hi": "मुझे वह जिला नहीं मिला। कृपया वर्तनी जांचें या इन गुजरात जिलों में से किसी एक को आज़माएं:",
        "gu": "મને તે જિલ્લો મળ્યો નથી. કૃપા કરીને સ્પેલિંગ તપાસો અથવા આ ગુજરાત જિલ્લાઓમાંથી કોઈ એકનો પ્રયાસ કરો:"
    },
    "did_you_mean": {
        "en": "Did you mean",
        "hi": "क्या आपका मतलब था",
        "gu": "શું તમારો મતલબ હતો"
    }
}

RESTRICTED_QUERY_RESPONSE = {
    "en": "I can only help with weather forecasts, mandi commodity prices, and vegetable disease detection for Gujarat. Please ask about these topics only.",
    "hi": "मैं केवल गुजरात के लिए मौसम पूर्वानुमान, मंडी कमोडिटी की कीमतें और सब्जी रोग का पता लगाने में मदद कर सकता हूं। कृपया केवल इन विषयों के बारे में पूछें।",
    "gu": "હું ફક્ત ગુજરાત માટે હવામાન આગાહી, માંડી કોમોડિટી ભાવ અને શાકભાજીના રોગોની ઓળખ માટે જ મદદ કરી શકું છું. કૃપા કરીને ફક્ત આ વિષયો વિશે જ પૂછો."
}

def find_free_port():
    """Find a free port starting from 5000"""
    for port in range(5000, 6000):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    return 5000  # fallback

def normalize_language_code(lang):
    lang = lang.lower().replace('-', '').replace('_', '')
    if 'gu' in lang or 'gujarati' in lang:
        return 'gu'
    elif 'hi' in lang or 'hindi' in lang:
        return 'hi'
    else:
        return 'en'

def create_response(message, data=None, status=200, error=None):
   response_data = {
       "message": message,
       "data": data if data is not None else {},
       "status": status
   }
   
   if error:
       response_data["data"] = {"error": error}
   
   return jsonify(response_data), status

def get_request_data():
   try:
       if request.is_json:
           return request.get_json() or {}
       elif request.form:
           return dict(request.form)
       else:
           try:
               raw_data = request.get_data()
               if raw_data:
                   try:
                       json_str = raw_data.decode('utf-8')
                       import json
                       return json.loads(json_str)
                   except (UnicodeDecodeError, json.JSONDecodeError):
                       return request.get_json(force=True) or {}
               return {}
           except:
               return {}
   except Exception as e:
       print(f"Error parsing request data: {e}")
       return {}

def allowed_file(filename):
   return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_image_to_supported_format(image_bytes):
   try:
       image = Image.open(io.BytesIO(image_bytes))
       
       if image.mode in ('RGBA', 'LA', 'P'):
           background = Image.new('RGB', image.size, (255, 255, 255))
           if image.mode == 'P':
               image = image.convert('RGBA')
           background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
           image = background
       elif image.mode != 'RGB':
           image = image.convert('RGB')
       
       if image.width > MAX_IMAGE_DIMENSION or image.height > MAX_IMAGE_DIMENSION:
           image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
       
       buffer = io.BytesIO()
       image.save(buffer, format='JPEG', quality=85, optimize=True)
       
       print(f"Image converted to JPEG, dimensions: {image.size}")
       return buffer.getvalue()
   except Exception as e:
       print(f"Error converting image: {e}")
       raise

def translate_disease_text(text: str, target_language: str) -> str:
    """Manual translation function for disease names"""
    try:
        if target_language == "en":
            return text
        elif target_language == "gu":
            if text == "Tomato Anthracnose":
                return "ટામેટા એન્થ્રેકનોઝ રોગ"
            elif text == "Tomato Early Blight":
                return "ટમેટામાં વહેલું ટપકું"
            elif text == "Tomato Powdery Mildew":
                return "ટામેટાનો ભૂકી છારો"
            else:
                return "અપ્રસ્તુત"
        elif target_language == "hi":
            if text == "Tomato Anthracnose":
                return "टमाटर एन्थ्रेक्नोज"
            elif text == "Tomato Early Blight":
                return "टमाटर का शीघ्र झुलसा रोग"
            elif text == "Tomato Powdery Mildew":
                return "टमाटर पाउडरी फफूंदी"
            else:
                return "अप्रासंगिक"
        else:
            return text
    except Exception as e:
        print(f"Disease text translation error: {e}")
        return text

def translate_text(text, target_language):
   if target_language == 'en':
       return text
   
   try:
       if target_language == 'hi':
           translator = GoogleTranslator(source='english', target='hindi')
       elif target_language == 'gu':
           translator = GoogleTranslator(source='english', target='gujarati')
       else:
           return text
       
       # Clean and validate input text
       cleaned_text = text.strip()
       if not cleaned_text:
           return text
       
       # Split long text into smaller chunks if needed
       max_chunk_length = 500
       if len(cleaned_text) > max_chunk_length:
           sentences = cleaned_text.split('\n')
           translated_sentences = []
           
           for sentence in sentences:
               if sentence.strip():
                   for attempt in range(3):
                       try:
                           translated_sentence = translator.translate(sentence.strip())
                           if translated_sentence and len(translated_sentence.strip()) > 0:
                               translated_sentences.append(translated_sentence.strip())
                               break
                       except Exception as e:
                           print(f"Sentence translation attempt {attempt + 1} failed: {e}")
                           if attempt == 2:  # Last attempt
                               translated_sentences.append(sentence)  # Keep original
           
           return '\n'.join(translated_sentences)
       else:
           # Try translation with retry mechanism for shorter text
           for attempt in range(3):
               try:
                   translated = translator.translate(cleaned_text)
                   if translated and len(translated.strip()) > 0:
                       # Additional validation for completeness
                       if len(translated.strip()) >= len(cleaned_text) * 0.3:  # At least 30% of original length
                           return translated.strip()
                   print(f"Translation attempt {attempt + 1} incomplete for: {cleaned_text[:50]}...")
               except Exception as e:
                   print(f"Translation attempt {attempt + 1} error: {e}")
                   continue
           
           # If all attempts fail, return original text
           print(f"All translation attempts failed for text: {cleaned_text[:50]}...")
           return text
           
   except Exception as e:
       print(f"Translation error: {e}")
       return text

def get_weather_data(lat, lon):
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
   base_url = "https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24"
   params = {
       "api-key": "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b",
       "format": "json",
       "filters[State]": "Gujarat",
       "limit": "1000"  # Increased limit to get more recent data
   }
   
   if district:
       params["filters[District]"] = district
   
   # Enhanced date filtering - prioritize recent data
   current_year = datetime.now().year
   
   try:
       response = requests.get(base_url, params=params)
       response.raise_for_status()
       api_data = response.json()
       records = api_data.get('records', [])
       
       if records:
           # Filter and sort records to get the most recent data
           valid_records = []
           
           for record in records:
               arrival_date_str = record.get('Arrival_Date', '')
               if arrival_date_str:
                   try:
                       # Parse date in DD/MM/YYYY format
                       arrival_date = datetime.strptime(arrival_date_str, '%d/%m/%Y')
                       record['parsed_date'] = arrival_date
                       
                       # Filter records from the last 3 years to get more relevant data
                       if arrival_date.year >= (current_year - 3):
                           valid_records.append(record)
                   except ValueError:
                       # Skip records with invalid date format
                       continue
           
           # Sort by date (most recent first)
           valid_records.sort(key=lambda x: x.get('parsed_date', datetime.min), reverse=True)
           
           if not valid_records:
               # If no recent records, try without date filtering but limit to recent years
               for record in records[:50]:  # Check first 50 records
                   arrival_date_str = record.get('Arrival_Date', '')
                   if arrival_date_str:
                       try:
                           arrival_date = datetime.strptime(arrival_date_str, '%d/%m/%Y')
                           if arrival_date.year >= (current_year - 5):  # Expand to 5 years
                               valid_records.append(record)
                       except ValueError:
                           continue
           
           if valid_records:
               records = valid_records[:10]  # Take top 10 most recent records
           else:
               # Fallback: take any available records but prefer recent ones
               records = records[:5]
       
       if not records:
           no_data_msg = "No recent commodity price data found for the selected criteria."
           if language != 'en':
               try:
                   no_data_msg = translate_text(no_data_msg, language)
               except:
                   pass
           
           return create_response(
               "No commodity price data found", 
               data={
                   "type": "commodity",
                   "response": no_data_msg, 
                   "records": []
               }, 
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
           data={
               "type": "commodity",
               "response": response_text, 
               "records": records
           }, 
           status=200
       )
       
   except Exception as e:
       return create_response(
           "Failed to retrieve commodity prices", 
           error=f"Error fetching commodity data: {e}", 
           status=500
       )

def format_commodity_response(records, district, date):
   if not records:
       return "No commodity price data found."
   
   response = f"Recent commodity prices"
   if district:
       response += f" in {district}, Gujarat"
   response += ":\n\n"
   
   for i, record in enumerate(records[:5]):
       arrival_date = record.get('Arrival_Date', 'N/A')
       response += f"{i+1}. {record.get('Commodity', 'N/A')} ({record.get('Variety', 'N/A')})\n"
       response += f"   Market: {record.get('Market', 'N/A')}\n"
       response += f"   Date: {arrival_date}\n"
       response += f"   Price Range: ₹{record.get('Min_Price', 'N/A')} - ₹{record.get('Max_Price', 'N/A')}\n"
       response += f"   Modal Price: ₹{record.get('Modal_Price', 'N/A')}\n\n"
   
   if len(records) > 5:
       response += f"... and {len(records) - 5} more items.\n"
   
   response += "\nNote: Prices shown are from the most recent available data."
   
   return response

def is_query_allowed(text):
    restricted_keywords = [
        'joke', 'story', 'poem', 'recipe', 'song', 'movie', 'game', 'politics', 
        'news', 'religion', 'philosophy', 'personal', 'relationship', 'advice',
        'programming', 'code', 'technology', 'sports', 'entertainment', 'travel',
        'education', 'history', 'science', 'mathematics', 'literature', 'art'
    ]
    
    allowed_keywords = [
        'weather', 'temperature', 'rain', 'forecast', 'climate', 'humid', 'wind',
        'price', 'commodity', 'market', 'cost', 'rate', 'mandi', 'bazaar',
        'disease', 'crop', 'vegetable', 'farming', 'agriculture', 'plant',
        'potato', 'tomato', 'onion', 'cotton', 'wheat', 'rice',
        'હવામાન', 'તાપમાન', 'વરસાદ', 'કિંમત', 'બજાર', 'રોગ', 'ખેતી', 'બટાટા', 'ટમેટા',
        'मौसम', 'तापमान', 'बारिश', 'कीमत', 'बाजार', 'बीमारी', 'खेती', 'आलू', 'टमाटर'
    ]
    
    text_lower = text.lower()
    
    has_restricted = any(keyword in text_lower for keyword in restricted_keywords)
    has_allowed = any(keyword in text_lower for keyword in allowed_keywords)
    
    return has_allowed and not has_restricted

def get_claude_response(message, context="", language="en"):
   if not claude_client:
       return "Chat service is not available."
   
   if not is_query_allowed(message):
       return RESTRICTED_QUERY_RESPONSE[language]
   
   try:
       system_prompt = f"""You are a specialized assistant for Gujarat, India farmers. You ONLY help with:
1. Weather forecasts for Gujarat districts
2. Mandi commodity prices in Gujarat
3. Vegetable disease identification

STRICT RULES:
- Answer ONLY in {language.upper()} language ({'English' if language == 'en' else 'Hindi' if language == 'hi' else 'Gujarati'})
- Do NOT answer questions about: jokes, stories, general knowledge, technology, politics, entertainment, or any non-agricultural topics
- If asked about unrelated topics, respond: "{RESTRICTED_QUERY_RESPONSE[language]}"
- Keep responses under 100 words
- Focus only on Gujarat agriculture, weather, and mandi prices
- When discussing commodity prices, acknowledge that data may be from recent years due to API limitations
- For Gujarati queries about vegetables like બટાટા (potato), provide helpful agricultural information"""
       
       full_context = f"{context}\n\nUser: {message}" if context else message
       
       response = claude_client.messages.create(
           model="claude-3-7-sonnet-20250219",
           max_tokens=150,
           temperature=0.3,
           system=system_prompt,
           messages=[{"role": "user", "content": full_context}]
       )
       
       return response.content[0].text
   except Exception as e:
       print(f"Error with Claude API: {e}")
       return "Sorry, I'm having trouble processing your request."

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_closest_district(user_input, threshold=0.5):
    """Enhanced district matching with better pronunciation handling"""
    user_input_lower = user_input.lower().strip()
    
    # First, try exact matches from our enhanced variations
    if user_input_lower in DISTRICT_NAME_VARIATIONS:
        return {
            'district': DISTRICT_NAME_VARIATIONS[user_input_lower], 
            'confidence': 1.0, 
            'matched_text': user_input_lower
        }
    
    # Check if any variation is contained in the user input
    for variation, district in DISTRICT_NAME_VARIATIONS.items():
        if variation in user_input_lower or user_input_lower in variation:
            confidence = 0.9 if variation in user_input_lower else 0.8
            return {
                'district': district,
                'confidence': confidence,
                'matched_text': variation
            }
    
    # Fuzzy matching with all variations
    best_matches = []
    for variation, district in DISTRICT_NAME_VARIATIONS.items():
        full_similarity = similarity(user_input_lower, variation)
        
        # Word-level matching for better results
        words = user_input_lower.split()
        word_similarities = [similarity(word, variation) for word in words]
        max_word_similarity = max(word_similarities) if word_similarities else 0
        
        best_similarity = max(full_similarity, max_word_similarity)
        
        if best_similarity >= threshold:
            best_matches.append({
                'district': district,
                'confidence': best_similarity,
                'matched_text': variation,
                'similarity_score': best_similarity
            })
    
    if best_matches:
        # Sort by confidence and return the best match
        best_matches.sort(key=lambda x: x['similarity_score'], reverse=True)
        return best_matches[0]
    
    return None

def get_popular_districts_list(language):
    popular_districts = {
        'en': ['Ahmedabad', 'Surat', 'Vadodara', 'Rajkot', 'Gandhinagar', 'Jamnagar'],
        'hi': ['अहमदाबाद', 'सूरत', 'वडोदरा', 'राजकोट', 'गांधीनगर', 'जामनगर'],
        'gu': ['અમદાવાદ', 'સુરત', 'વડોદરા', 'રાજકોટ', 'ગાંધીનગર', 'જામનગર']
    }
    
    return popular_districts.get(language, popular_districts['en'])

def extract_location_from_command(command):
    """Enhanced location extraction with better pronunciation support"""
    command_lower = command.lower().strip()
    
    # Try direct lookup first
    location_info = find_closest_district(command_lower, threshold=0.5)
    if location_info:
        return location_info
    
    # Additional phonetic variations for common mispronunciations
    phonetic_variations = {
        'rajcot': 'Rajkot',
        'rajkott': 'Rajkot',
        'surat': 'Surat',
        'surath': 'Surat',
        'ahmdabad': 'Ahmedabad',
        'ahemdabad': 'Ahmedabad',
        'vadodra': 'Vadodara',
        'vadodara': 'Vadodara',
        'baroda': 'Vadodara'
    }
    
    for phonetic, district in phonetic_variations.items():
        if phonetic in command_lower:
            return {'district': district, 'confidence': 0.9}
    
    return None

def is_weather_query(text_lower):
   weather_keywords = [
       'weather', 'temperature', 'rain', 'forecast', 'climate', 'humid', 'wind',
       'hot', 'cold', 'sunny', 'cloudy', 'storm', 'precipitation', 'degrees',
       'celsius', 'fahrenheit', 'mausam', 'hava', 'barish', 'thand', 'garmi',
       'હવામાન', 'તાપમાન', 'વરસાદ', 'ઠંડી', 'ગરમી', 'આબોહવા', 'મૌસમ'
   ]
   return any(keyword in text_lower for keyword in weather_keywords)

def is_commodity_query(text_lower):
   commodity_keywords = [
       'price', 'commodity', 'market', 'cost', 'rate', 'mandi', 'bazaar',
       'sell', 'buy', 'crops', 'vegetables', 'fruits', 'agriculture',
       'farming', 'harvest', 'produce', 'wholesale', 'retail',
       'potato', 'tomato', 'onion', 'cotton', 'wheat', 'rice',
       'किमत', 'दाम', 'मंडी', 'बाजार', 'फसल', 'खेती', 'आलू', 'टमाटर',
       'કિંમત', 'દર', 'માંડી', 'બજાર', 'પાક', 'ખેતી', 'બટાટા', 'ટમેટા'
   ]
   return any(keyword in text_lower for keyword in commodity_keywords)

def handle_disease_detection(language):
   try:
       raw_image_bytes = None
       
       if 'file' in request.files:
           file = request.files['file']
           
           if file.filename == '':
               error_msg = "Please select a file to upload"
               if language != 'en':
                   try:
                       error_msg = translate_text(error_msg, language)
                   except:
                       pass
               return create_response(
                   "No file selected",
                   error=error_msg,
                   status=400
               )
           
           raw_image_bytes = file.read()
           
       elif request.json and 'image' in request.json:
           try:
               image_data = base64.b64decode(request.json['image'])
               raw_image_bytes = image_data
           except Exception as e:
               error_msg = "Failed to decode base64 image"
               if language != 'en':
                   try:
                       error_msg = translate_text(error_msg, language)
                   except:
                       pass
               return create_response(
                   "Invalid base64 image data",
                   error=error_msg,
                   status=400
               )
       else:
           error_msg = "Please upload an image file or provide base64 image data"
           if language != 'en':
               try:
                   error_msg = translate_text(error_msg, language)
               except:
                   pass
           return create_response(
               "No image provided",
               error=error_msg,
               status=400
           )
       
       if not rekognition:
           lang_code = language if language in ['en', 'hi', 'gu'] else 'en'
           return create_response(
               DISEASE_MESSAGES["invalid_image"][lang_code],
               error="AWS Rekognition service not configured",
               status=503
           )
       
       print(f"Processing disease detection image of size: {len(raw_image_bytes)}")
       
       try:
           image_bytes = convert_image_to_supported_format(raw_image_bytes)
       except Exception as e:
           lang_code = language if language in ['en', 'hi', 'gu'] else 'en'
           return create_response(
               DISEASE_MESSAGES["unsupported_format"][lang_code],
               error="Failed to process image format",
               status=415
           )
       
       response = rekognition.detect_custom_labels(
           ProjectVersionArn=MODEL_ARN,
           Image={'Bytes': image_bytes}
       )
       
       print("AWS Rekognition Response:", response)
       
       final_response = response.get("CustomLabels", [])
       lang_code = language if language in ['en', 'hi', 'gu'] else 'en'
       
       if not final_response or (final_response and final_response[0]["Name"] == "Irrelevant"):
           return create_response(
               DISEASE_MESSAGES["no_disease"][lang_code],
               data={
                   "type": "disease_detection",
                   "predictions": [],
                   "response": DISEASE_MESSAGES["no_disease"][lang_code]
               },
               status=200
           )
       
       valid_labels = []
       disease_names = []
       
       for label in final_response:
           original_name = label["Name"]
           translated_name = translate_disease_text(original_name, lang_code)
           
           valid_labels.append({
               "label": translated_name,
               "confidence": label["Confidence"],
               "original_label": original_name
           })
           disease_names.append(translated_name)
       
       # Create a comprehensive response message
       if len(disease_names) == 1:
           if lang_code == 'hi':
               response_msg = f"पहचाना गया रोग: {disease_names[0]}"
           elif lang_code == 'gu':
               response_msg = f"ઓળખાયેલ રોગ: {disease_names[0]}"
           else:
               response_msg = f"Detected disease: {disease_names[0]}"
       else:
           diseases_list = ", ".join(disease_names)
           if lang_code == 'hi':
               response_msg = f"पहचाने गए रोग: {diseases_list}"
           elif lang_code == 'gu':
               response_msg = f"ઓળખાયેલ રોગો: {diseases_list}"
           else:
               response_msg = f"Detected diseases: {diseases_list}"
       
       return create_response(
           DISEASE_MESSAGES["success"][lang_code],
           data={
               "type": "disease_detection",
               "predictions": valid_labels,
               "response": response_msg,
               "disease_count": len(valid_labels)
           },
           status=200
       )
       
   except Exception as e:
       print(f"Disease detection error: {str(e)}")
       lang_code = language if language in ['en', 'hi', 'gu'] else 'en'
       error_msg = str(e)
       if lang_code != 'en':
           try:
               error_msg = translate_text(f"Error processing image: {str(e)}", lang_code)
           except:
               error_msg = DISEASE_MESSAGES["invalid_image"][lang_code]
       
       return create_response(
           DISEASE_MESSAGES["invalid_image"][lang_code],
           error=error_msg,
           status=422
       )

def handle_weather_query(original_text, text_lower, language):
    try:
        location_info = extract_location_from_command(text_lower)
        
        if location_info and location_info.get('confidence', 0) >= 0.7:
            district = location_info['district']
            coords = GUJARAT_DISTRICTS[district]
            weather_data = get_weather_data(coords['lat'], coords['lon'])
            
            if weather_data:
                response = format_weather_response(weather_data, district)
                
                if location_info.get('confidence', 1.0) < 0.9:
                    did_you_mean = DISTRICT_ERROR_MESSAGES["did_you_mean"][language]
                    response = f"({did_you_mean} {district}?)\n\n" + response
                
                if language != 'en':
                    try:
                        response = translate_text(response, language)
                    except Exception as e:
                        print(f"Weather translation failed: {e}")
                
                return create_response(
                    "Weather information retrieved successfully",
                    data={
                        "type": "weather",
                        "district": district,
                        "response": response,
                        "fuzzy_match": location_info.get('confidence', 1.0) < 0.9
                    },
                    status=200
                )
            else:
                error_msg = "Couldn't fetch weather data"
                if language != 'en':
                    try:
                        error_msg = translate_text(error_msg, language)
                    except:
                        pass
                
                return create_response(
                    "Failed to retrieve weather data",
                    error=error_msg,
                    status=500
                )
        
        elif location_info and location_info.get('confidence', 0) > 0.4:
            district = location_info['district']
            did_you_mean = DISTRICT_ERROR_MESSAGES["did_you_mean"][language]
            
            error_msg = f"{did_you_mean} {district}? Please confirm the district name."
            
            if language != 'en':
                try:
                    error_msg = translate_text(error_msg, language)
                except:
                    pass
            
            return create_response(
                "District name unclear",
                data={
                    "type": "clarification",
                    "suggested_district": district,
                    "response": error_msg
                },
                status=200
            )
        
        else:
            base_msg = DISTRICT_ERROR_MESSAGES["district_not_found"][language]
            popular_districts = get_popular_districts_list(language)
            districts_list = ", ".join(popular_districts)
            
            error_msg = f"{base_msg}\n{districts_list}"
            
            return create_response(
                "District not recognized",
                data={
                    "type": "error",
                    "response": error_msg,
                    "suggested_districts": popular_districts
                },
                status=200
            )
            
    except Exception as e:
        print(f"Weather query error: {str(e)}")
        return create_response(
            "Failed to process weather query",
            error=str(e),
            status=500
        )

def handle_commodity_query(original_text, text_lower, language):
   try:
       district = None
       location_info = extract_location_from_command(text_lower)
       
       if location_info and location_info.get('confidence', 0) >= 0.7:
           district = location_info['district']
       
       date_str = None
       
       return get_commodity_prices_internal(district, date_str, language)
       
   except Exception as e:
       print(f"Commodity query error: {str(e)}")
       return create_response(
           "Failed to process commodity query",
           error=str(e),
           status=500
       )

def handle_general_chat(text, language):
   try:
       if not is_query_allowed(text):
           return create_response(
               "Query not allowed",
               data={
                   "type": "chat",
                   "response": RESTRICTED_QUERY_RESPONSE[language]
               },
               status=200
           )
       
       # Enhance context for Gujarati vegetable queries
       enhanced_context = ""
       if language == 'gu' and any(veg in text.lower() for veg in ['બટાટા', 'ટમેટા', 'કાંદો']):
           enhanced_context = "User is asking about vegetables in Gujarati. Provide helpful agricultural information."
       
       if language != 'en':
           try:
               text_for_claude = translate_text(text, 'en')
           except Exception as e:
               print(f"Translation to English failed: {e}")
               text_for_claude = text
       else:
           text_for_claude = text
       
       response = get_claude_response(text_for_claude, enhanced_context, language)
       
       if not response:
           error_msg = "Unable to generate response"
           if language != 'en':
               try:
                   error_msg = translate_text(error_msg, language)
               except:
                   pass
           
           return create_response(
               "Failed to generate chat response",
               error=error_msg,
               status=500
           )
       
       return create_response(
           "Chat response generated successfully",
           data={
               "type": "chat",
               "response": response
           },
           status=200
       )
       
   except Exception as e:
       print(f"General chat error: {str(e)}")
       return create_response(
           "Failed to process chat query",
           error=str(e),
           status=500
       )

@app.route('/smart_assistant', methods=['POST'])
def smart_assistant():
   try:
       data = {}
       language = 'en'
       
       if request.content_type and 'multipart/form-data' in request.content_type:
           data = dict(request.form)
           language = data.get('language', 'en')
       else:
           data = get_request_data()
           language = data.get('language', 'en')
       
       language = normalize_language_code(language)
       
       if 'file' in request.files or (data and 'image' in data):
           return handle_disease_detection(language)
       
       text = data.get('text', '').strip()
       
       if not text:
           return create_response(
               "No input provided", 
               error="Please provide text input or upload an image", 
               status=400
           )
       
       text_lower = text.lower()
       
       if is_weather_query(text_lower):
           return handle_weather_query(text, text_lower, language)
       elif is_commodity_query(text_lower):
           return handle_commodity_query(text, text_lower, language)
       else:
           return handle_general_chat(text, language)
           
   except Exception as e:
       print(f"Smart assistant error: {str(e)}")
       return create_response(
           "Failed to process request", 
           error=f"An error occurred: {str(e)}", 
           status=500
       )

@app.route('/health', methods=['GET'])
def health_check():
   return create_response("Service is healthy", data={"status": "UP"}, status=200)

@app.route('/', methods=['GET'])
def root():
   return create_response(
       "Gujarat Smart Assistant API with Disease Detection", 
       data={
           "name": "Gujarat Smart Assistant API with Disease Detection",
           "version": "3.2.0",
           "description": "Enhanced intelligent API for Gujarat agriculture - weather, commodity prices, and disease detection with improved pronunciation handling",
           "main_endpoint": "/smart_assistant",
           "supported_languages": ["English (en)", "Hindi (hi)", "Gujarati (gu)"],
           "features": [
               "Enhanced pronunciation recognition for district names",
               "Improved date filtering for commodity prices",
               "Better Gujarati language support for vegetable queries",
               "Weather information for Gujarat districts",
               "Recent commodity/Mandi price information",
               "Vegetable disease detection using AI",
               "Multi-language support with proper translation",
               "Fuzzy district name matching for voice input"
           ]
       }, 
       status=200
   )

if __name__ == '__main__':
    port = find_free_port()
    
    print(f"\n🚀 Starting Enhanced Gujarat Smart Assistant API...")
    print(f"🌐 Running on: http://localhost:{port}")
    print(f"📍 Main endpoint: http://localhost:{port}/smart_assistant")
    print(f"🏥 Health check: http://localhost:{port}/health")
    
    if port != 5000:
        print(f"⚠️  Note: Port 5000 was occupied, using port {port} instead")
    
    try:
        app.run(host='0.0.0.0', debug=True, port=port)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {port} is also in use. Trying to find another port...")
            port = find_free_port()
            app.run(host='0.0.0.0', debug=True, port=port)
        else:
            raise
