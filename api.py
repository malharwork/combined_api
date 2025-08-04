from flask import Flask, request, jsonify
import requests
import os
import io
import boto3
from datetime import datetime
import anthropic
from deep_translator import GoogleTranslator
from dotenv import load_dotenv
import base64
from flask_cors import CORS
from PIL import Image
from difflib import SequenceMatcher
import re

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

COMMODITY_MAPPING = {
    'tomato': 'Tomato',
    'onion': 'Onion',
    'potato': 'Potato',
    'brinjal': 'Brinjal',
    'eggplant': 'Brinjal',
    'okra': 'Bhindi',
    'ladyfinger': 'Bhindi',
    'cabbage': 'Cabbage',
    'cauliflower': 'Cauliflower',
    'carrot': 'Carrot',
    'beans': 'Beans',
    'peas': 'Peas',
    'spinach': 'Spinach',
    'coriander': 'Coriander',
    'mint': 'Mint',
    'chilli': 'Chili',
    'chili': 'Chili',
    'pepper': 'Chili',
    'garlic': 'Garlic',
    'ginger': 'Ginger',
    'cucumber': 'Cucumber',
    'bottle gourd': 'Bottle gourd',
    'ridge gourd': 'Ridge gourd',
    'bitter gourd': 'Bitter gourd',
    'pumpkin': 'Pumpkin',
    'wheat': 'Wheat',
    'rice': 'Rice',
    'bajra': 'Bajra',
    'jowar': 'Jowar',
    'cotton': 'Cotton',
    'groundnut': 'Groundnut',
    'peanut': 'Groundnut',
    'sesame': 'Sesame',
    'mustard': 'Mustard',
    'cumin': 'Cumin',
    'coriander seed': 'Coriander seed',
    'turmeric': 'Turmeric',
    'fenugreek': 'Fenugreek',
    'castor seed': 'Castor seed',
    'टमाटर': 'Tomato',
    'प्याज': 'Onion',
    'आलू': 'Potato',
    'बैंगन': 'Brinjal',
    'भिंडी': 'Bhindi',
    'पत्तागोभी': 'Cabbage',
    'फूलगोभी': 'Cauliflower',
    'गाजर': 'Carrot',
    'बीन्स': 'Beans',
    'मटर': 'Peas',
    'पालक': 'Spinach',
    'धनिया': 'Coriander',
    'पुदीना': 'Mint',
    'मिर्च': 'Chili',
    'लहसुन': 'Garlic',
    'अदरक': 'Ginger',
    'खीरा': 'Cucumber',
    'लौकी': 'Bottle gourd',
    'तोरी': 'Ridge gourd',
    'करेला': 'Bitter gourd',
    'कद्दू': 'Pumpkin',
    'गेहूं': 'Wheat',
    'चावल': 'Rice',
    'बाजरा': 'Bajra',
    'ज्वार': 'Jowar',
    'कपास': 'Cotton',
    'मूंगफली': 'Groundnut',
    'तिल': 'Sesame',
    'सरसों': 'Mustard',
    'जीरा': 'Cumin',
    'धनिया बीज': 'Coriander seed',
    'हल्दी': 'Turmeric',
    'मेथी': 'Fenugreek',
    'अरंडी': 'Castor seed',
    'ટમેટા': 'Tomato',
    'ટમાટર': 'Tomato',
    'ડુંગળી': 'Onion',
    'બટાકા': 'Potato',
    'રીંગણ': 'Brinjal',
    'ભીંડા': 'Bhindi',
    'કોબી': 'Cabbage',
    'ફૂલકોબી': 'Cauliflower',
    'ગાજર': 'Carrot',
    'શીંગ': 'Beans',
    'વટાણા': 'Peas',
    'પાલક': 'Spinach',
    'કોથમીર': 'Coriander',
    'ફુદીનો': 'Mint',
    'મરચું': 'Chili',
    'લસણ': 'Garlic',
    'આદુ': 'Ginger',
    'કાકડી': 'Cucumber',
    'દૂધી': 'Bottle gourd',
    'તુરીયા': 'Ridge gourd',
    'કારેલા': 'Bitter gourd',
    'કોળું': 'Pumpkin',
    'ઘઉં': 'Wheat',
    'ચોખા': 'Rice',
    'બાજરી': 'Bajra',
    'જુવાર': 'Jowar',
    'કપાસ': 'Cotton',
    'મગફળી': 'Groundnut',
    'તલ': 'Sesame',
    'સરસવ': 'Mustard',
    'જીરું': 'Cumin',
    'કોથમીર બીજ': 'Coriander seed',
    'હળદર': 'Turmeric',
    'મેથી': 'Fenugreek',
    'એરંડ': 'Castor seed'
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
    },
    "commodity_not_found": {
        "en": "I couldn't find that commodity. Please check the spelling or try searching for common vegetables like tomato, onion, potato.",
        "hi": "मुझे वह कमोडिटी नहीं मिली। कृपया वर्तनी जांचें या टमाटर, प्याज, आलू जैसी सामान्य सब्जियों की खोज करें।",
        "gu": "મને તે કોમોડિટી મળી નથી. કૃપા કરીને સ્પેલિંગ તપાસો અથવા ટમેટા, ડુંગળી, બટાકા જેવી સામાન્ય શાકભાજીની શોધ કરો."
    },
    "district_required": {
        "en": "Please specify a Gujarat district to get commodity prices. For example: 'tomato price in Ahmedabad' or 'onion rates in Surat'",
        "hi": "कृपया कमोडिटी की कीमतें पाने के लिए गुजरात जिला निर्दिष्ट करें। उदाहरण: 'अहमदाबाद में टमाटर की कीमत' या 'सूरत में प्याज के दाम'",
        "gu": "કૃપા કરીને કોમોડિટીના ભાવ મેળવવા માટે ગુજરાત જિલ્લો સ્પષ્ટ કરો. ઉદાહરણ: 'અમદાવાદમાં ટમેટાની કિંમત' અથવા 'સુરતમાં ડુંગળીના રેટ'"
    },
    "commodity_required": {
        "en": "Please specify which commodity/vegetable price you want to check. For example: 'tomato price in Ahmedabad' or 'onion rates in Surat'",
        "hi": "कृपया बताएं कि आप किस कमोडिटी/सब्जी की कीमत जांचना चाहते हैं। उदाहरण: 'अहमदाबाद में टमाटर की कीमत' या 'सूरत में प्याज के दाम'",
        "gu": "કૃપા કરીને સ્પષ્ટ કરો કે તમે કઈ કોમોડિટી/શાકભાજીની કિંમત તપાસવા માંગો છો. ઉદાહરણ: 'અમદાવાદમાં ટમેટાની કિંમત' અથવા 'સુરતમાં ડુંગળીના રેટ'"
    }
}

RESTRICTED_QUERY_RESPONSE = {
    "en": "I can only help with weather forecasts, mandi commodity prices, and vegetable disease detection for Gujarat. Please ask about these topics only.",
    "hi": "मैं केवल गुजरात के लिए मौसम पूर्वानुमान, मंडी कमोडिटी की कीमतें और सब्जी रोग का पता लगाने में मदद कर सकता हूं। कृपया केवल इन विषयों के बारे में पूछें।",
    "gu": "હું ફક્ત ગુજરાત માટે હવામાન આગાહી, માંડી કોમોડિટી ભાવ અને શાકભાજીના રોગોની ઓળખ માટે જ મદદ કરી શકું છું. કૃપા કરીને ફક્ત આ વિષયો વિશે જ પૂછો."
}

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
       
       cleaned_text = text.strip()
       if not cleaned_text:
           return text
       
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
                           if attempt == 2:
                               translated_sentences.append(sentence)
           
           return '\n'.join(translated_sentences)
       else:
           for attempt in range(3):
               try:
                   translated = translator.translate(cleaned_text)
                   if translated and len(translated.strip()) > 0:
                       if len(translated.strip()) >= len(cleaned_text) * 0.3:
                           return translated.strip()
                   print(f"Translation attempt {attempt + 1} incomplete for: {cleaned_text[:50]}...")
               except Exception as e:
                   print(f"Translation attempt {attempt + 1} error: {e}")
                   continue
           
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

def extract_commodity_from_text(text):
    text_lower = text.lower().strip()
    
    for key, value in COMMODITY_MAPPING.items():
        if key.lower() in text_lower:
            return value
    
    best_match = None
    best_score = 0.6
    
    for key, value in COMMODITY_MAPPING.items():
        words = text_lower.split()
        for word in words:
            score = similarity(word, key.lower())
            if score > best_score:
                best_match = value
                best_score = score
    
    return best_match

def get_commodity_prices_internal(district, date_str, language, commodity=None):
   base_url = "https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24"
   params = {
       "api-key": "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b",
       "format": "json",
       "filters[State]": "Gujarat",
       "limit": "100"
   }
   
   if district:
       params["filters[District]"] = district
   
   if commodity:
       params["filters[Commodity]"] = commodity
       print(f"Filtering by commodity: {commodity}")
   
   if date_str:
       try:
           date_obj = datetime.strptime(date_str, '%Y-%m-%d')
           formatted_date = date_obj.strftime('%d/%m/%Y')
           params["filters[Arrival_Date]"] = formatted_date
       except ValueError:
           pass
   
   try:
       print(f"API Request params: {params}")
       response = requests.get(base_url, params=params)
       response.raise_for_status()
       api_data = response.json()
       records = api_data.get('records', [])
       
       print(f"Found {len(records)} records")
       
       if not records:
           no_data_msg = "No commodity price data found for the selected criteria."
           if commodity:
               if language == 'hi':
                   no_data_msg = f"{commodity} के लिए कोई मंडी भाव नहीं मिला।"
               elif language == 'gu':
                   no_data_msg = f"{commodity} માટે કોઈ માંડી ભાવ મળ્યો નથી."
               else:
                   no_data_msg = f"No mandi prices found for {commodity}."
           
           if language != 'en' and not commodity:
               try:
                   no_data_msg = translate_text(no_data_msg, language)
               except:
                   pass
           
           return create_response(
               "No commodity price data found", 
               data={
                   "type": "commodity",
                   "response": no_data_msg, 
                   "records": [],
                   "filters_applied": {
                       "district": district,
                       "commodity": commodity,
                       "date": date_str
                   }
               }, 
               status=200
           )
       else:
           response_text = format_commodity_response(records, district, date_str, commodity)
       
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
               "records": records,
               "total_records": len(records),
               "filters_applied": {
                   "district": district,
                   "commodity": commodity,
                   "date": date_str
               }
           }, 
           status=200
       )
       
   except Exception as e:
       print(f"Commodity API error: {e}")
       return create_response(
           "Failed to retrieve commodity prices", 
           error=f"Error fetching commodity data: {e}", 
           status=500
       )

def format_commodity_response(records, district, date, commodity=None):
   if not records:
       return "No commodity price data found."
   
   response = f"Commodity prices"
   if commodity:
       response += f" for {commodity}"
   if district:
       response += f" in {district}, Gujarat"
   if date:
       response += f" for {date}"
   response += ":\n\n"
   
   commodity_groups = {}
   for record in records:
       comm_name = record.get('Commodity', 'Unknown')
       if comm_name not in commodity_groups:
           commodity_groups[comm_name] = []
       commodity_groups[comm_name].append(record)
   
   count = 0
   max_display = 10
   
   for comm_name, comm_records in commodity_groups.items():
       if count >= max_display:
           break
           
       response += f"📊 {comm_name}:\n"
       
       for i, record in enumerate(comm_records[:3]):
           count += 1
           response += f"   • Market: {record.get('Market', 'N/A')}\n"
           if record.get('Variety', 'N/A') != 'N/A':
               response += f"     Variety: {record.get('Variety', 'N/A')}\n"
           response += f"     Price Range: ₹{record.get('Min_Price', 'N/A')} - ₹{record.get('Max_Price', 'N/A')}\n"
           response += f"     Modal Price: ₹{record.get('Modal_Price', 'N/A')}\n"
           if record.get('Arrival_Date'):
               response += f"     Date: {record.get('Arrival_Date', 'N/A')}\n"
           response += "\n"
           
           if count >= max_display:
               break
       
       if len(comm_records) > 3:
           response += f"   ... and {len(comm_records) - 3} more markets for {comm_name}\n\n"
   
   if len(records) > max_display:
       response += f"... and {len(records) - count} more records available.\n"
   
   return response

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

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
        'હવામાન', 'તાપમાન', 'વરસાદ', 'કિંમત', 'બજાર', 'રોગ', 'ખેતી',
        'मौसम', 'तापमान', 'बारिश', 'कीमत', 'बाजार', 'बीमारी', 'खेती'
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
- Focus only on Gujarat agriculture, weather, and mandi prices"""
       
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

def find_closest_district(user_input, threshold=0.6):
    user_input_lower = user_input.lower().strip()
    
    all_districts = {}
    
    for district in GUJARAT_DISTRICTS:
        all_districts[district] = district
    
    gujarati_districts = {
        'અમદાવાદ': 'Ahmedabad',
        'અમરેલી': 'Amreli', 
        'આણંદ': 'Anand',
        'અરાવલી': 'Aravalli',
        'બનાસકાંઠા': 'Banaskantha',
        'ભરૂચ': 'Bharuch',
        'ભાવનગર': 'Bhavnagar',
        'બોટાદ': 'Botad',
        'છોટા ઉદયપુર': 'Chhota Udaipur',
        'દાહોદ': 'Dahod',
        'દાંગ': 'Dang',
        'દેવભૂમિ દ્વારકા': 'Devbhoomi Dwarka',
        'ગાંધીનગર': 'Gandhinagar',
        'ગીર સોમનાથ': 'Gir Somnath',
        'જામનગર': 'Jamnagar',
        'જૂનાગઢ': 'Junagadh',
        'ખેડા': 'Kheda',
        'કચ્છ': 'Kutch',
        'મહિસાગર': 'Mahisagar',
        'મહેસાણા': 'Mehsana',
        'મોરબી': 'Morbi',
        'નર્મદા': 'Narmada',
        'નવસારી': 'Navsari',
        'પંચમહાલ': 'Panchmahal',
        'પાટણ': 'Patan',
        'પોરબંદર': 'Porbandar',
        'રાજકોટ': 'Rajkot',
        'સાબરકાંઠા': 'Sabarkantha',
        'સુરત': 'Surat',
        'સુરેન્દ્રનગર': 'Surendranagar',
        'તાપી': 'Tapi',
        'વડોદરા': 'Vadodara',
        'વલસાડ': 'Valsad'
    }
    
    for gujarati_name, english_name in gujarati_districts.items():
        all_districts[gujarati_name] = english_name
    
    district_variations = {
        'amdavad': 'Ahmedabad',
        'baroda': 'Vadodara',
        'kachchh': 'Kutch'
    }
    
    for variation, district in district_variations.items():
        all_districts[variation] = district
    
    for name, english_name in all_districts.items():
        if name.lower() in user_input_lower:
            return {'district': english_name, 'confidence': 1.0, 'matched_text': name}
    
    best_matches = []
    for name, english_name in all_districts.items():
        full_similarity = similarity(user_input_lower, name.lower())
        
        words = user_input_lower.split()
        word_similarities = [similarity(word, name.lower()) for word in words]
        max_word_similarity = max(word_similarities) if word_similarities else 0
        
        best_similarity = max(full_similarity, max_word_similarity)
        
        if best_similarity >= threshold:
            best_matches.append({
                'district': english_name,
                'confidence': best_similarity,
                'matched_text': name,
                'similarity_score': best_similarity
            })
    
    if best_matches:
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

def get_popular_commodities_list(language):
    popular_commodities = {
        'en': ['Tomato', 'Onion', 'Potato', 'Brinjal', 'Bhindi', 'Cabbage'],
        'hi': ['टमाटर', 'प्याज', 'आलू', 'बैंगन', 'भिंडी', 'पत्तागोभी'],
        'gu': ['ટમેટા', 'ડુંગળી', 'બટાકા', 'રીંગણ', 'ભીંડા', 'કોબી']
    }
    
    return popular_commodities.get(language, popular_commodities['en'])

def extract_location_from_command(command):
    command_lower = command.lower().strip()
    
    gujarati_districts = {
        'અમદાવાદ': 'Ahmedabad',
        'અમરેલી': 'Amreli', 
        'આણંદ': 'Anand',
        'અરાવલી': 'Aravalli',
        'બનાસકાંઠા': 'Banaskantha',
        'ભરૂચ': 'Bharuch',
        'ભાવનગર': 'Bhavnagar',
        'બોટાદ': 'Botad',
        'છોટા ઉદયપુર': 'Chhota Udaipur',
        'દાહોદ': 'Dahod',
        'દાંગ': 'Dang',
        'દેવભૂમિ દ્વારકા': 'Devbhoomi Dwarka',
        'ગાંધીનગર': 'Gandhinagar',
        'ગીર સોમનાથ': 'Gir Somnath',
        'જામનગર': 'Jamnagar',
        'જૂનાગઢ': 'Junagadh',
        'ખેડા': 'Kheda',
        'કચ્છ': 'Kutch',
        'મહિસાગર': 'Mahisagar',
        'મહેસાણા': 'Mehsana',
        'મોરબી': 'Morbi',
        'નર્મદા': 'Narmada',
        'નવસારી': 'Navsari',
        'પંચમહાલ': 'Panchmahal',
        'પાટણ': 'Patan',
        'પોરબંદર': 'Porbandar',
        'રાજકોટ': 'Rajkot',
        'સાબરકાંઠા': 'Sabarkantha',
        'સુરત': 'Surat',
        'સુરેન્દ્રનગર': 'Surendranagar',
        'તાપી': 'Tapi',
        'વડોદરા': 'Vadodara',
        'વલસાડ': 'Valsad'
    }
    
    for gujarati_name, english_name in gujarati_districts.items():
        if gujarati_name in command_lower:
            return {'district': english_name, 'confidence': 1.0}
    
    for district in GUJARAT_DISTRICTS:
        if district.lower() in command_lower:
            return {'district': district, 'confidence': 1.0}
    
    district_variations = {
        'amdavad': 'Ahmedabad',
        'baroda': 'Vadodara',
        'kachchh': 'Kutch'
    }
    
    for variation, district in district_variations.items():
        if variation in command_lower:
            return {'district': district, 'confidence': 1.0}
    
    return find_closest_district(command)

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
       'किमत', 'दाम', 'मंडी', 'बाजार', 'फसल', 'खेती',
       'કિંમત', 'દર', 'માંડી', 'બજાર', 'પાક', 'ખેતી', 'ભાવ'
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
        
        if location_info and location_info.get('confidence', 0) >= 0.8:
            district = location_info['district']
            coords = GUJARAT_DISTRICTS[district]
            weather_data = get_weather_data(coords['lat'], coords['lon'])
            
            if weather_data:
                response = format_weather_response(weather_data, district)
                
                if location_info.get('confidence', 1.0) < 1.0:
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
                        "fuzzy_match": location_info.get('confidence', 1.0) < 1.0
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
        
        if location_info and location_info.get('confidence', 0) >= 0.6:
            district = location_info['district']
        
        commodity = extract_commodity_from_text(original_text)
        print(f"Extracted commodity: {commodity} from text: {original_text}")
        
        if not district:
            base_msg = DISTRICT_ERROR_MESSAGES["district_required"][language]
            popular_districts = get_popular_districts_list(language)
            districts_list = ", ".join(popular_districts)
            
            error_msg = f"{base_msg}\n\nSuggested districts: {districts_list}"
            
            return create_response(
                "District required for commodity prices",
                data={
                    "type": "error",
                    "response": error_msg,
                    "suggested_districts": popular_districts,
                    "error_type": "district_required"
                },
                status=200
            )
        
        if not commodity:
            base_msg = DISTRICT_ERROR_MESSAGES["commodity_required"][language]
            popular_commodities = get_popular_commodities_list(language)
            commodities_list = ", ".join(popular_commodities)
            
            error_msg = f"{base_msg}\n\nSuggested commodities: {commodities_list}"
            
            return create_response(
                "Commodity required for price check",
                data={
                    "type": "error",
                    "response": error_msg,
                    "suggested_commodities": popular_commodities,
                    "error_type": "commodity_required"
                },
                status=200
            )
        
        date_str = None
        
        return get_commodity_prices_internal(district, date_str, language, commodity)
        
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
       
       if language != 'en':
           try:
               text = translate_text(text, 'en')
           except Exception as e:
               print(f"Translation to English failed: {e}")
       
       response = get_claude_response(text, "", language)
       
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
       "Gujarat Smart Assistant API with Enhanced Commodity Filtering", 
       data={
           "name": "Gujarat Smart Assistant API with Enhanced Commodity Filtering",
           "version": "3.2.0",
           "description": "Enhanced intelligent API for Gujarat agriculture with granular commodity filtering - weather, specific commodity prices, and disease detection",
           "main_endpoint": "/smart_assistant",
           "supported_languages": ["English (en)", "Hindi (hi)", "Gujarati (gu)"],
           "features": [
               "Restricted query processing (agriculture only)",
               "Weather information for Gujarat districts",
               "Granular commodity/Mandi price filtering by specific crops",
               "Support for commodity queries in Gujarati, Hindi, and English",
               "Vegetable disease detection using AI",
               "Multi-language support with proper translation",
               "Fuzzy district name matching for voice input",
               "Enhanced commodity extraction from natural language queries"
           ],
           "supported_commodities": list(set(COMMODITY_MAPPING.values())),
           "example_queries": {
               "english": ["What is the price of tomato in Ahmedabad?", "Show me onion rates in Surat"],
               "hindi": ["अहमदाबाद में टमाटर की कीमत क्या है?", "सूरत में प्याज के दाम बताएं"],
               "gujarati": ["અમદાવાદમાં ટમેટાનો ભાવ કેટલો છે?", "સુરતમાં ડુંગળીના રેટ બતાવો"]
           }
       }, 
       status=200
   )

if __name__ == '__main__':
   app.run(host='0.0.0.0', debug=True, port=5000)
