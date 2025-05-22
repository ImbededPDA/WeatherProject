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

# ✅ 날씨 + 미세먼지 + 조언 가져오기
def get_weather_report(lat, lon, city):
    API_KEY = "53c8a3c7700b8b529deac9d34468ac87"  # ← OpenWeatherMap 키 입력
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    air_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"

    try:
        weather_res = requests.get(weather_url).json()
        air_res = requests.get(air_url).json()

        weather = weather_res["weather"][0]["main"]
        temp = round(weather_res["main"]["temp"])
        pm25 = air_res["list"][0]["components"]["pm2_5"]

        pm25_status = (
            "좋음" if pm25 < 16 else
            "보통" if pm25 < 36 else
            "나쁨" if pm25 < 76 else
            "매우 나쁨"
        )

        advice = ""
        if weather == "Clear":
            advice = "맑은 날에는 자외선 차단제를 꼭 바르세요."
        elif weather == "Rain":
            advice = "비 오는 날엔 습도가 높아 트러블이 생기기 쉬워요. 수분 조절이 중요합니다."
        elif weather == "Dust":
            advice = "미세먼지가 많으니 외출 후 세안을 꼼꼼히 해주세요."
        else:
            advice = "오늘은 보습과 진정 중심의 피부 관리가 좋습니다."

        today = datetime.now().strftime("%Y년 %m월 %d일")
        report = (
            f"오늘은 {today}, 현재 위치는 {city}입니다. "
            f"현재 기온은 {temp}도이고, 날씨는 {weather}입니다. "
            f"미세먼지 농도는 {pm25:.1f} 마이크로그램으로 '{pm25_status}' 수준입니다. "
            f"{advice}"
        )
        return report

    except Exception as e:
        return "날씨 정보를 가져오는 데 문제가 발생했습니다."

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
