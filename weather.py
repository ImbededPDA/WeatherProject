import speech_recognition as sr
#import pyttsx3
import os
from gtts import gTTS
import requests
from datetime import datetime
from flask import Flask, jsonify, render_template
from flask_cors import CORS
import threading
import subprocess
# Flask 앱 생성
app = Flask(__name__)
CORS(app)

# ✅ TTS 엔진 초기화
#engine = pyttsx3.init()
#engine.setProperty('rate', 150)
# ✅ TTS 출력 (gTTS 기반)
def speak(text):
    print(f"[📢] {text}")
    tts = gTTS(text=text, lang='ko')
    tts.save("/tmp/speech.mp3")
    subprocess.run(["mpg321", "/tmp/speech.mp3"])
"""
def speak(text):
    print(f"[📢] {text}")
    engine.say(text)
    engine.runAndWait()
"""
# ✅ 위치 기반 위도, 경도 가져오기 (IP 기반)
def get_location():
    try:
        res = requests.get("https://ipinfo.io/json")
        data = res.json()
        loc = data["loc"].split(",")
        lat, lon = float(loc[0]), float(loc[1])
        city = data.get("city", "지역")
        return lat, lon, city
    except:
        return None, None, "알 수 없는 지역"

# ✅ 날씨/기온/습도 조언 함수
def get_skin_advice(weather, temp, humidity):
    advice_parts = []

    # 날씨
    if weather == "Clear":
        advice_parts.append("맑은 날에는 자외선 차단제를 꼭 바르세요.")
    elif weather == "Clouds":
        advice_parts.append("흐린 날에도 자외선 차단제를 사용하는 것이 좋아요.")
    elif weather == "Rain":
        advice_parts.append("비가 오는 날에는 외출 후 이중 세안을 추천합니다.")
    elif weather == "Snow":
        advice_parts.append("눈 오는 날엔 피부가 트지 않도록 고보습 케어를 하세요.")
    else:
        advice_parts.append("현재 날씨에 맞는 기초 케어를 유지하세요.")

    # 기온
    if temp >= 30:
        advice_parts.append("기온이 높아 유분이 많아질 수 있으므로 수분 보충이 중요해요.")
    elif 20 <= temp < 30:
        advice_parts.append("적당한 기온으로 기본 수분 관리에 집중하세요.")
    elif 10 <= temp < 20:
        advice_parts.append("선선한 날씨에는 유수분 균형이 필요합니다.")
    elif 0 <= temp < 10:
        advice_parts.append("기온이 낮아 피부가 건조해질 수 있으니 고보습 제품을 사용하세요.")
    else:
        advice_parts.append("매우 추운 날씨에는 피부 장벽을 보호하는 고보습 제품이 필수입니다.")

    # 습도
    if humidity >= 80:
        advice_parts.append("습도가 높아 피부에 유분이 증가할 수 있으니 산뜻한 수분 제품을 사용하세요.")
    elif 60 <= humidity < 80:
        advice_parts.append("수분과 유분의 밸런스를 맞춘 관리가 필요합니다.")
    elif 40 <= humidity < 60:
        advice_parts.append("적당한 습도로 일반적인 루틴을 유지하시면 됩니다.")
    elif 20 <= humidity < 40:
        advice_parts.append("건조한 날씨에는 미스트나 슬리핑 팩 등을 활용하세요.")
    else:
        advice_parts.append("매우 건조하므로 세라마이드 함유 보습제를 사용하는 것이 좋아요.")

    return " ".join(advice_parts)

# ✅ 미세먼지 조언 함수
def get_dust_advice(pm25):
    if pm25 <= 15:
        return "미세먼지가 적은 날이므로 평소처럼 기초 루틴을 유지하셔도 좋아요."
    elif pm25 <= 35:
        return "보통 수준이니 외출 후에는 가볍게 세안하고 진정 케어를 해주세요."
    elif pm25 <= 75:
        return "미세먼지가 많아 모공 막힘이 우려됩니다. 이중 세안과 진정 팩을 추천드려요."
    else:
        return "미세먼지가 매우 많아 외출 시 마스크 착용이 필수이며, 귀가 후 꼼꼼한 클렌징이 필요합니다."

# ✅ 시간별 루틴 생성 함수
def generate_morning_routine(weather, temp, humidity, pm25):
    routines = []
    
    # 날씨 기반
    if weather == "Clear":
        routines.append("🌞 자외선 차단 필수! SPF50+ 선크림 추천")
    elif weather == "Rain":
        routines.append("🌂 비 올 때는 산뜻한 워터프루프 선크림")
    
    # 온도 기반
    if temp >= 30:
        routines.append("🧴 가벼운 수분 젤 타입 선크림")
    elif temp <= 10:
        routines.append("❄️ 보습 강화 겨울용 선크림")
    
    # 미세먼지 기반
    if pm25 > 35:
        routines.append("😷 미세먼지 차단을 위한 클렌징 폼 사용")
    
    return " • ".join(routines) if routines else "기본 아침 루틴을 추천드려요"

def generate_evening_routine(weather, temp, humidity, pm25):
    routines = []
    
    # 습도 기반
    if humidity < 40:
        routines.append("💦 히알루론산 세럼 강화")
    elif humidity > 70:
        routines.append("🌿 피지 조절 토너 사용")
    
    # 온도 기반
    if temp >= 25:
        routines.append("🧼 오일 클렌징으로 모공 관리")
    
    # 미세먼지 기반
    if pm25 > 50:
        routines.append("✨ 미세먼지 제거를 위한 더블 클렌징")
    
    return " • ".join(routines) if routines else "기본 저녁 루틴을 추천드려요"

# ✅ 날씨 + 미세먼지 + 조언 통합 (웹용 데이터 반환)
def get_weather_data(lat, lon, city):
    API_KEY = "53c8a3c7700b8b529deac9d34468ac87"
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    air_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"

    try:
        weather_res = requests.get(weather_url).json()
        air_res = requests.get(air_url).json()

        weather = weather_res["weather"][0]["main"]
        temp = round(weather_res["main"]["temp"])
        humidity = weather_res["main"]["humidity"]
        city = weather_res["name"]
        pm25 = air_res["list"][0]["components"]["pm2_5"]

        pm25_status = (
            "좋음" if pm25 < 16 else
            "보통" if pm25 < 36 else
            "나쁨" if pm25 < 76 else
            "매우 나쁨"
        )

        # 조언 구성
        weather_advice = get_skin_advice(weather, temp, humidity)
        dust_advice = get_dust_advice(pm25)
        combined_advice = f"{weather_advice} {dust_advice}"

        # 시간별 루틴 생성
        morning_routine = generate_morning_routine(weather, temp, humidity, pm25)
        evening_routine = generate_evening_routine(weather, temp, humidity, pm25)

        date_str = datetime.now().strftime("%Y년 %m월 %d일")
        
        return {
            "temperature": temp,
            "humidity": humidity,
            "weather": weather,
            "pm25": pm25,
            "pm25_status": pm25_status,
            "advice": combined_advice,
            "city": city,
            "date": date_str,
            "morning_routine": morning_routine,
            "evening_routine": evening_routine,
            "full_report": f"오늘은 {date_str}, {city}의 현재 기온은 {temp}도이며 날씨는 {weather}입니다. 습도는 {humidity}%, 미세먼지 농도는 {pm25:.1f}μg/m³로 '{pm25_status}' 수준입니다. {combined_advice}"
        }

    except Exception as e:
        print(f"날씨 API 오류: {e}")
        return None

# ✅ 음성 명령 인식 및 처리
def listen_for_weather_question():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    try:
        with mic as source:
            print("🎤 음성 인식 중...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)

        command = recognizer.recognize_google(audio, language='ko-KR')
        print(f"[🎧 인식된 명령어]: {command}")
        return command

    except sr.UnknownValueError:
        return "음성을 인식하지 못했어요. 다시 말씀해주세요."
    except sr.RequestError:
        return "음성 인식 서버에 연결할 수 없습니다."
    except sr.WaitTimeoutError:
        return "음성 입력 시간이 초과되었습니다."

# ✅ Flask 라우트 추가
@app.route('/')
def index():
    return render_template('home_ui.html')

@app.route('/weather')
def weather_api():
    lat, lon, city = get_location()
    if lat is not None:
        weather_data = get_weather_data(lat, lon, city)
        if weather_data:
            return jsonify(weather_data)
    
    return jsonify({
        "error": "날씨 정보를 가져올 수 없습니다.",
        "temperature": "--",
        "humidity": "--"
    })

@app.route('/voice-command')
def voice_command():
    command = listen_for_weather_question()
    
    if "날씨" in command:
        lat, lon, city = get_location()
        if lat is not None:
            weather_data = get_weather_data(lat, lon, city)
            if weather_data:
                # TTS를 별도 스레드에서 실행 (논블로킹)
                threading.Thread(target=speak, args=(weather_data['full_report'],)).start()
                return jsonify({
                    "command": command,
                    "response": weather_data['full_report'],
                    "weather_data": weather_data
                })
        
        error_msg = "위치 정보를 가져오는 데 실패했습니다."
        threading.Thread(target=speak, args=(error_msg,)).start()
        return jsonify({
            "command": command,
            "response": error_msg
        })
    else:
        response_msg = "날씨에 대한 질문을 해주세요."
        threading.Thread(target=speak, args=(response_msg,)).start()
        return jsonify({
            "command": command,
            "response": response_msg
        })

# ✅ 실행
if __name__ == "__main__":
    print("🌐 피부관리 조언 시스템 웹 서버를 시작합니다...")
    print("📱 브라우저에서 http://localhost:5000 으로 접속하세요")
    app.run(host='0.0.0.0', port=5000, debug=True)

