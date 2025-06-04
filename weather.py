import speech_recognition as sr
from gtts import gTTS
import requests
from datetime import datetime
from flask import Flask, jsonify, render_template
from flask_cors import CORS
import threading
import subprocess
import time

app = Flask(__name__)
CORS(app)

# 🔥 전역 상태 변수
is_listening_for_wakeword = True
is_listening_for_command = False
command_lock = threading.Lock()

# ✅ TTS 출력 (gTTS 기반)
def speak(text):
    print(f"[📢] {text}")
    tts = gTTS(text=text, lang='ko')
    tts.save("/tmp/speech.mp3")
    subprocess.run(["mpg321", "/tmp/speech.mp3"])

# 현재 시간대 반환
def get_time_period():
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 23:
        return "evening"
    else:
        return "night"

# 영어 날씨 → 한글 변환
def translate_weather_to_korean(weather):
    return {
        "Clear": "맑음",
        "Clouds": "흐림",
        "Rain": "비",
        "Snow": "눈",
        "Drizzle": "이슬비",
        "Thunderstorm": "뇌우",
        "Mist": "안개",
        "Fog": "안개",
        "Haze": "실안개"
    }.get(weather, "알 수 없음")

# IP로 위치 정보 가져오기
def get_location():
    try:
        res = requests.get("https://ipinfo.io/json")
        data = res.json()
        lat, lon = map(float, data["loc"].split(","))
        city = data.get("city", "지역")
        return lat, lon, city
    except:
        return None, None, "알 수 없는 지역"

# 날씨 + 온도 + 습도에 따른 피부관리 조언
def get_skin_advice(weather, temp, humidity):
    advice = []
    if weather == "Clear":
        advice.append("맑은 날에는 자외선 차단제를 꼭 바르세요.")
    elif weather == "Clouds":
        advice.append("흐린 날에도 자외선 차단제를 사용하는 것이 좋아요.")
    elif weather == "Rain":
        advice.append("비가 오는 날에는 외출 후 이중 세안을 추천합니다.")
    elif weather == "Snow":
        advice.append("눈 오는 날엔 피부가 트지 않도록 고보습 케어를 하세요.")
    else:
        advice.append("현재 날씨에 맞는 기초 케어를 유지하세요.")

    if temp >= 30:
        advice.append("기온이 높아 유분이 많아질 수 있으므로 수분 보충이 중요해요.")
    elif 20 <= temp < 30:
        advice.append("적당한 기온으로 기본 수분 관리에 집중하세요.")
    elif 10 <= temp < 20:
        advice.append("선선한 날씨에는 유수분 균형이 필요합니다.")
    elif 0 <= temp < 10:
        advice.append("기온이 낮아 피부가 건조해질 수 있으니 고보습 제품을 사용하세요.")
    else:
        advice.append("매우 추운 날씨에는 피부 장벽을 보호하는 고보습 제품이 필수입니다.")

    if humidity >= 80:
        advice.append("습도가 높아 피부에 유분이 증가할 수 있으니 산뜻한 수분 제품을 사용하세요.")
    elif 60 <= humidity < 80:
        advice.append("수분과 유분의 밸런스를 맞춘 관리가 필요합니다.")
    elif 40 <= humidity < 60:
        advice.append("적당한 습도로 일반적인 루틴을 유지하시면 됩니다.")
    elif 20 <= humidity < 40:
        advice.append("건조한 날씨에는 미스트나 슬리핑 팩 등을 활용하세요.")
    else:
        advice.append("매우 건조하므로 세라마이드 함유 보습제를 사용하는 것이 좋아요.")
    return " ".join(advice)

# 미세먼지 농도 기반 조언
def get_dust_advice(pm25):
    if pm25 <= 15:
        return "미세먼지가 적은 날이므로 평소처럼 기초 루틴을 유지하셔도 좋아요."
    elif pm25 <= 35:
        return "보통 수준이니 외출 후에는 가볍게 세안하고 진정 케어를 해주세요."
    elif pm25 <= 75:
        return "미세먼지가 많아 모공 막힘이 우려됩니다. 이중 세안과 진정 팩을 추천드려요."
    else:
        return "미세먼지가 매우 많아 외출 시 마스크 착용이 필수이며, 귀가 후 꼼꼼한 클렌징이 필요합니다."

# 날씨 API 호출
def get_weather_data(lat, lon, city):
    API_KEY = "53c8a3c7700b8b529deac9d34468ac87"
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    air_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    try:
        weather = requests.get(weather_url).json()
        air = requests.get(air_url).json()
        temp = round(weather["main"]["temp"])
        humidity = weather["main"]["humidity"]
        weather_main = weather["weather"][0]["main"]
        translated = translate_weather_to_korean(weather_main)
        pm25 = air["list"][0]["components"]["pm2_5"]
        status = "좋음" if pm25 < 16 else "보통" if pm25 < 36 else "나쁨" if pm25 < 76 else "매우 나쁨"
        skin = get_skin_advice(weather_main, temp, humidity)
        dust = get_dust_advice(pm25)
        date_str = datetime.now().strftime("%Y년 %m월 %d일")
        return f"{date_str}, {city}의 기온은 {temp}도, 날씨는 {translated}, 습도는 {humidity}%, 미세먼지 {pm25:.1f}μg/m³({status})입니다. {skin} {dust}"
    except Exception as e:
        print(f"[API 오류] {e}")
        return "날씨 정보를 가져오는 데 실패했어요."

# 🎯 명령어 처리 함수 (공통)
def process_voice_command():
    """음성 명령을 인식하고 처리하는 공통 함수"""
    global is_listening_for_wakeword, is_listening_for_command
    
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    
    try:
        with mic as source:
            speak("네 말씀하세요")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=5)
            command = recognizer.recognize_google(audio, language='ko-KR')
            print(f"[명령어 인식] {command}")
            
            if "날씨" in command:
                lat, lon, city = get_location()
                result = get_weather_data(lat, lon, city)
                speak(result)
                return {"command": command, "response": result}
            else:
                speak("날씨에 대한 질문을 해주세요.")
                return {"command": command, "response": "날씨에 대한 질문을 해주세요."}
                
    except Exception as e:
        print(f"[명령어 인식 오류] {e}")
        speak("죄송합니다. 다시 말씀해 주세요.")
        return {"command": "none", "response": "음성 인식 실패"}
    
    finally:
        # 명령어 처리 완료 후 다시 대기어 듣기 모드로 복귀
        with command_lock:
            is_listening_for_command = False
            is_listening_for_wakeword = True
        print("🔄 대기어 듣기 모드로 복귀")

# 🎤 대기어 인식 루프 (백그라운드)
def voice_wakeup_loop():
    global is_listening_for_wakeword, is_listening_for_command
    
    recognizer = sr.Recognizer()
    
    while True:
        try:
            # 대기어 듣기 모드가 활성화되어 있을 때만 실행
            if is_listening_for_wakeword and not is_listening_for_command:
                mic = sr.Microphone()  # 새로운 마이크 인스턴스
                with mic as source:
                    print("🎤 호출어 '시리' 대기 중...")
                    recognizer.adjust_for_ambient_noise(source, duration=1)
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    command = recognizer.recognize_google(audio, language='ko-KR')
                    print(f"[대기어 감지] {command}")
                    
                    if "시리" in command:
                        # 대기어 인식 시 모드 전환
                        with command_lock:
                            is_listening_for_wakeword = False
                            is_listening_for_command = True
                        
                        print("✅ 대기어 인식됨! 명령어 듣기 모드로 전환")
                        process_voice_command()
            else:
                # 명령어 듣기 모드일 때는 잠시 대기
                time.sleep(0.5)
                
        except Exception as e:
            print(f"[대기어 인식 오류] {e}")
            time.sleep(2)  # 오류 발생 시 2초 대기

# 🌐 웹 버튼 클릭 → 바로 명령어 듣기
@app.route("/voice-command")
def voice_command():
    global is_listening_for_wakeword, is_listening_for_command
    
    # 웹 버튼 클릭 시 대기어 듣기 우회하고 바로 명령어 모드로
    with command_lock:
        is_listening_for_wakeword = False
        is_listening_for_command = True
    
    print("🌐 웹 버튼 클릭 - 바로 명령어 듣기 모드")
    result = process_voice_command()
    return jsonify(result)

# 🏠 기본 웹 페이지
@app.route("/")
def index():
    return render_template("home_ui.html")


# 🚀 서버 실행
if __name__ == "__main__":
    print("🌐 서버 시작: http://localhost:5000")
    print("🎤 음성 대기어 시스템 활성화")
    
    # 대기어 인식 루프를 백그라운드에서 실행
    threading.Thread(target=voice_wakeup_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)