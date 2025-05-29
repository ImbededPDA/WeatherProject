import speech_recognition as sr
import pyttsx3
import requests
from datetime import datetime

# ✅ TTS 엔진 초기화
engine = pyttsx3.init()
engine.setProperty('rate', 150)

def speak(text):
    print(f"[📢] {text}")
    engine.say(text)
    engine.runAndWait()

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

# ✅ 날씨 + 미세먼지 + 조언 통합
def get_weather_report(lat, lon, city):
    API_KEY = "53c8a3c7700b8b529deac9d34468ac87"  # ← 너의 OpenWeatherMap API Key
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

        date_str = datetime.now().strftime("%Y년 %m월 %d일")
        report = (
            f"오늘은 {date_str}, {city}의 현재 기온은 {temp}도이며 날씨는 {weather}입니다. "
            f"습도는 {humidity}%, 미세먼지 농도는 {pm25:.1f}μg/m³로 '{pm25_status}' 수준입니다. "
            f"{weather_advice} {dust_advice}"
        )
        return report

    except Exception as e:
        return "날씨 정보를 가져오는 데 실패했습니다."

# ✅ 음성 명령 인식 및 처리
def listen_for_weather_question():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    with mic as source:
        print("🎤 '오늘 날씨 어때?'라고 말해주세요...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

    try:
        command = recognizer.recognize_google(audio, language='ko-KR')
        print(f"[🎧 인식된 명령어]: {command}")

        if "날씨" in command:
            lat, lon, city = get_location()
            if lat is not None:
                report = get_weather_report(lat, lon, city)
                speak(report)
            else:
                speak("위치 정보를 가져오는 데 실패했습니다.")
        else:
            speak("죄송해요. 날씨에 대한 질문만 인식할 수 있어요.")
    except sr.UnknownValueError:
        speak("음성을 인식하지 못했어요. 다시 말씀해주세요.")
    except sr.RequestError:
        speak("음성 인식 서버에 연결할 수 없습니다.")

# ✅ 실행
if __name__ == "__main__":
    listen_for_weather_question()
