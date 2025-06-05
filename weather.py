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
current_tts_proc = None

# ✅ TTS 출력 (gTTS 기반)
def speak(text):
    """
    text를 TTS(mp3)로 변환하여 재생한다.
    재생 중 '그만'이라는 단어가 감지되면, 재생 프로세스를 중단하도록 listen_for_stopword 스레드를 띄움.
    """
    global current_tts_proc

    # 1) mp3 파일 생성
    print(f"[📢] {text}")
    tts = gTTS(text=text, lang='ko')
    mp3_path = "/tmp/speech.mp3"
    tts.save(mp3_path)

    # 2) 비동기 재생 프로세스 시작 (subprocess.Popen)
    try:
        # 기존 프로세스가 있으면 안전하게 종료
        if current_tts_proc is not None and current_tts_proc.poll() is None:
            current_tts_proc.kill()
            current_tts_proc = None

        # mpg321을 이용해 mp3 재생 (백그라운드)
        current_tts_proc = subprocess.Popen(
            ["mpg321", "-q", mp3_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"[TTS 재생 오류] {e}")
        current_tts_proc = None
        return

    # 3) “그만” 단어 감지를 위한 별도 스레드 실행 (데몬)
    stop_listener = threading.Thread(target=listen_for_stopword, daemon=True)
    stop_listener.start()


def listen_for_stopword():
    """
    TTS 재생 중 마이크로 “그만”이라는 단어가 감지되면, current_tts_proc을 종료한다.
    """
    global current_tts_proc

    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    with mic as source:
        # 주변 소음 레벨 파악
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            while True:
                # 1) 현재 TTS가 재생 중인지 확인
                if current_tts_proc is None or current_tts_proc.poll() is not None:
                    # 재생이 끝났거나 중단된 상태이면 스레드 종료
                    return

                # 2) 음성 청취 (짧게)
                audio = recognizer.listen(source, timeout=2, phrase_time_limit=3)
                try:
                    command = recognizer.recognize_google(audio, language='ko-KR')
                    print(f"[종료어 감지 시도] {command}")
                    if "그만" in command:
                        # “그만”이 감지되면 재생 중인 프로세스 강제 종료
                        if current_tts_proc is not None and current_tts_proc.poll() is None:
                            print("[TTS 중단] '그만'이 감지되어 TTS 재생을 중단합니다.")
                            current_tts_proc.kill()
                            current_tts_proc = None
                        return
                except sr.UnknownValueError:
                    # 인식 실패(무음 등) -> 계속 대기
                    continue
                except sr.RequestError as e:
                    print(f"[음성 인식 오류] {e}")
                    return
        except Exception as e:
            print(f"[종료어 감지 루프 오류] {e}")
            return
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
def generate_morning_routine(weather, temp, humidity, pm25):
    routines = []
    
    # 날씨별 기본 루틴
    if weather == "Clear":
        routines.append("🌞 맑은 아침: 자외선 차단 필수! SPF50+ 선크림")
    elif weather == "Clouds":
        routines.append("☁️ 흐린 아침: UV차단 + 가벼운 보습")
    elif weather == "Rain":
        routines.append("🌂 비 오는 아침: 워터프루프 선크림 필수")
    else:
        routines.append("🌅 기본 아침 루틴: 클렌징 + 보습 + 자외선 차단")
    
    # 온도별 추가 케어
    if temp >= 30:
        routines.append("🧴 고온: 가벼운 수분 젤 타입 제품 사용")
    elif temp >= 25:
        routines.append("☀️ 따뜻한 날: 산뜻한 로션 타입 추천")
    elif temp <= 10:
        routines.append("❄️ 추운 날: 보습 강화 겨울용 크림")
    else:
        routines.append("🌤️ 선선한 날: 적당한 보습력 크림")
    
    # 습도별 추가 케어
    if humidity < 40:
        routines.append("💧 건조한 아침: 히알루론산 세럼 + 보습 미스트")
    elif humidity > 70:
        routines.append("🌿 습한 아침: 산뜻한 젤 타입 + 피지조절 토너")
    else:
        routines.append("💦 적정 습도: 수분-유분 밸런스 케어")
    
    # 미세먼지별 추가 케어
    if pm25 > 50:
        routines.append("😷 미세먼지 나쁨: 항산화 세럼 + 보호막 크림")
    elif pm25 > 35:
        routines.append("🛡️ 미세먼지 보통: 비타민C 세럼 추천")
    else:
        routines.append("🌬️ 공기 깨끗: 기본 안티에이징 케어")
    
    return "\n".join(routines)  # • 대신 줄바꿈으로 변경


def generate_evening_routine(weather, temp, humidity, pm25):
    routines = []
    
    # 날씨별 기본 루틴
    if weather == "Clear":
        routines.append("🌙 맑은 저녁: 이중 클렌징 + 보습 크림")
    elif weather == "Clouds":
        routines.append("☁️ 흐린 저녁: 부드러운 클렌징 + 수분 공급")
    elif weather == "Rain":
        routines.append("🌧️ 비 온 저녁: 깊은 클렌징 + 진정 케어")
    else:
        routines.append("🌃 기본 저녁 루틴: 클렌징 + 수분 공급")
    
    # 온도별 추가 케어
    if temp >= 30:
        routines.append("🔥 고온: 오일 클렌징 + 시원한 토너팩")
    elif temp >= 25:
        routines.append("☀️ 따뜻한 날: 폼 클렌징 + 수분 밸런싱")
    elif temp <= 10:
        routines.append("❄️ 추운 날: 오일 클렌징 + 고보습 크림")
    else:
        routines.append("🌙 선선한 날: 이중 클렌징 + 영양 크림")
    
    # 습도별 추가 케어
    if humidity < 40:
        routines.append("💧 건조함: 히알루론산 세럼 3중 보습")
    elif humidity > 70:
        routines.append("🌿 습함: 피지 조절 토너 + 수분 젤")
    else:
        routines.append("💦 적정 습도: 수분크림 + 밸런싱 에센스")
    
    # 미세먼지별 추가 케어
    if pm25 > 50:
        routines.append("😷 미세먼지 나쁨: 더블 클렌징 + 항산화 마스크")
    elif pm25 > 35:
        routines.append("✨ 미세먼지 보통: 딥 클렌징 + 보호 크림")
    else:
        routines.append("🌬️ 공기 깨끗: 기본 클렌징 + 수분 팩")
    
    return "\n".join(routines)
def get_routine_advice():
    period = get_time_period()
    if period == "morning":
        return "🌞 아침 루틴: 자외선 차단제 필수, 가벼운 보습 추천!", period
    elif period == "afternoon":
        return "☀️ 오후 루틴: 미스트로 수분 보충, 선크림 덧바르기!", period
    elif period == "evening":
        return "🌙 저녁 루틴: 이중 클렌징, 고보습 크림 사용!", period
    else:
        return "🌃 밤 루틴: 수면팩, 진정 케어로 마무리!", period

# 날씨 API 호출
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
        translated = translate_weather_to_korean(weather)
        city = weather_res["name"]
        pm25 = air_res["list"][0]["components"]["pm2_5"]
        
        pm25_status = (
            "좋음" if pm25 < 16 else
            "보통" if pm25 < 36 else
            "나쁨" if pm25 < 76 else
            "매우 나쁨"
        )

        weather_advice = get_skin_advice(weather, temp, humidity)
        dust_advice = get_dust_advice(pm25)
        combined_advice = f"{weather_advice} {dust_advice}"

        date_str = datetime.now().strftime("%Y년 %m월 %d일")
        routine_advice, routine_time = get_routine_advice()
        morning_routine = generate_morning_routine(weather, temp, humidity, pm25)
        evening_routine = generate_evening_routine(weather, temp, humidity, pm25)
        
        return {
            "temperature": temp,
            "humidity": humidity,
            "weather": weather,
            "pm25": pm25,
            "pm25_status": pm25_status,
            "advice": combined_advice,
            "city": city,
            "date": date_str,
            "routine_time": routine_time,
            "routine_advice": routine_advice,
            "morning_routine": morning_routine,
            "evening_routine": evening_routine,
            "translated": translated,
            "full_report": f"오늘은 {date_str}, {city}의 현재 기온은 {temp}도이며 날씨는 {translated}입니다. 습도는 {humidity}%, 미세먼지 농도는 {pm25:.1f}μg/m³로 '{pm25_status}' 수준입니다. {combined_advice}"

        }
    except Exception as e:
        print(f"[API 오류] {e}")
        return None
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
                if result:
                    speak(result["full_report"])  # ✅ 요약된 날씨 정보만 말하게 수정
                    return {"command": command, "response": result["full_report"], "weather_data": result}
                else:
                    speak("날씨 정보를 불러올 수 없습니다.")
                    return {"command": command, "response": "날씨 정보를 불러올 수 없습니다."}

                
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
def convert_routine_to_checklist(routine_text, routine_type):
    """루틴 텍스트를 체크리스트 항목으로 변환"""
    items = []
    lines = routine_text.split('\n')
    
    for line in lines:
        if line.strip():
            # 각 라인을 체크리스트 항목으로 변환
            items.append({
                "id": f"{routine_type}_{len(items)}",
                "text": line.strip(),
                "completed": False,
                "category": extract_category(line)  # 날씨/온도/습도/미세먼지 구분
            })
    
    return items

def extract_category(text):
    """텍스트에서 카테고리 추출"""
    if "날씨" in text or "맑은" in text or "비" in text or "흐린" in text:
        return "weather"
    elif "온도" in text or "고온" in text or "추운" in text or "따뜻한" in text:
        return "temperature"
    elif "습도" in text or "건조" in text or "습한" in text:
        return "humidity"
    elif "미세먼지" in text:
        return "air_quality"
    else:
        return "general"

def get_today_weather_data():
    """날씨 데이터를 가져오는 함수"""
    lat, lon, city = get_location()
    if lat is not None:
        weather_data = get_weather_data(lat, lon, city)
        if weather_data:
            return (
                weather_data['weather'], 
                weather_data['temperature'], 
                weather_data['humidity'], 
                weather_data['pm25']
            )
    # 기본값 반환
    return "Clear", 20, 50, 30

@app.route('/daily-checklist')
def get_daily_checklist():
    try:
        # 수정된 함수 호출
        lat, lon, city = get_location()
        if lat is not None:
            weather_data = get_weather_data(lat, lon, city)
            if weather_data:
                weather = weather_data['weather']
                temp = weather_data['temperature']
                humidity = weather_data['humidity']
                pm25 = weather_data['pm25']
            else:
                # 기본값 설정
                weather, temp, humidity, pm25 = "Clear", 20, 50, 30
        else:
            weather, temp, humidity, pm25 = "Clear", 20, 50, 30
        
        # 아침/저녁 루틴을 체크리스트 항목으로 변환
        morning_items = convert_routine_to_checklist(
            generate_morning_routine(weather, temp, humidity, pm25), 
            "morning"
        )
        evening_items = convert_routine_to_checklist(
            generate_evening_routine(weather, temp, humidity, pm25), 
            "evening"
        )
        
        return jsonify({
            "date": datetime.now().strftime("%Y년 %m월 %d일"),
            "weather_info": f"{translate_weather_to_korean(weather)}, {temp}°C, 습도 {humidity}%, 미세먼지 {pm25}",
            "morning_checklist": morning_items,
            "evening_checklist": evening_items
        })
    except Exception as e:
        print(f"체크리스트 오류: {e}")
        return jsonify({"error": str(e)})
    
# 🚀 서버 실행
if __name__ == "__main__":
    print("🌐 서버 시작: http://localhost:5000")
    print("🎤 음성 대기어 시스템 활성화")
    
    # 대기어 인식 루프를 백그라운드에서 실행
    threading.Thread(target=voice_wakeup_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)