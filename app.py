from flask import Flask, request, jsonify, send_from_directory
from PIL import Image, ImageDraw, ImageFont, ImageStat
import openai
import os
import requests
from io import BytesIO

# Flask 서버 초기화
app = Flask(__name__)

# CORS 허용
from flask_cors import CORS
CORS(app)

# API 키 설정
openai.api_key = '여기에 api 입력'

# 'static' 폴더 생성
STATIC_FOLDER = 'static'
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

# 폰트 경로 설정
FONT_PATH = os.path.join(os.getcwd(), '/Users/syb/Downloads/Coding-Ping-Webpage-main/backend/fonts/NanumBrush.ttf')

def translate_text(text, target_language):
    """GPT를 사용해 텍스트를 원하는 언어로 번역합니다."""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Translate this to {target_language}: {text}"}]
    )
    return response.choices[0].message['content'].strip()

def summarize_message(text):
    """GPT를 사용해 영어 메시지를 간결하게 요약합니다."""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Summarize the following message briefly: {text}"}]
    )
    return response.choices[0].message['content'].strip()

def ask_gpt_for_text_position(image_description):
    """GPT에게 이미지 설명을 바탕으로 텍스트 배치 위치를 추천받습니다."""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Based on the following image description: '{image_description}', suggest where the text would be most visible (e.g., 'top left', 'center', 'bottom right')."}]
    )
    return response.choices[0].message['content'].strip()

def get_best_text_color(image):
    """이미지의 평균 밝기를 계산해 적절한 텍스트 색상을 결정합니다."""
    stat = ImageStat.Stat(image)
    r, g, b = stat.mean[:3]
    brightness = (r * 0.299 + g * 0.587 + b * 0.114)
    return 'black' if brightness > 128 else 'white'

def calculate_text_position(image, position_hint, text, font):
    """GPT가 제안한 위치에 따라 텍스트 좌표를 계산합니다."""
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_width = right - left
    text_height = bottom - top

    # 위치 힌트에 따라 좌표 계산
    if position_hint == 'top left':
        x, y = 10, 10
    elif position_hint == 'top right':
        x, y = image.width - text_width - 10, 10
    elif position_hint == 'bottom right':
        x, y = image.width - text_width - 10, image.height - text_height - 10
    elif position_hint == 'bottom left':
        x, y = 10, image.height - text_height - 10
    else:  # 기본적으로 중앙 배치
        x = (image.width - text_width) / 2
        y = (image.height - text_height) / 2

    # 텍스트가 이미지 밖으로 넘어가지 않도록 조정
    x = max(0, min(x, image.width - text_width))
    y = max(0, min(y, image.height - text_height))

    return x, y

# AI 이미지 생성 API 엔드포인트
@app.route('/generate', methods=['POST'])
def generate_image():
    try:
        data = request.json
        title = data.get('title', '제목 없음')
        message = data.get('message', '내용 없음')

        # 한글 → 영어 번역
        translated_message = translate_text(message, "English")

        # 영어 메시지 요약
        summarized_message = summarize_message(translated_message)

        # 요약된 영어 메시지를 다시 한글로 번역
        final_message = translate_text(summarized_message, "Korean")

        # 동적 프롬프트 생성 (이미지에 텍스트 포함하지 않도록 제약)
        prompt = (
            f"Create an artistic illustration for: '{translated_message}'. "
            f"Ensure the illustration contains no text, numbers, or any other written characters. Pick a keyword that you think is important in the message and draw it."
        )
        # DALL·E를 사용해 이미지 생성
        dalle_response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="512x512"
        )

        # 생성된 이미지 다운로드
        image_url = dalle_response['data'][0]['url']
        image_response = requests.get(image_url)
        img = Image.open(BytesIO(image_response.content))

        # GPT에게 텍스트 배치 위치 추천받기
        image_description = translated_message  # 이미지 설명으로 사용
        position_hint = ask_gpt_for_text_position(image_description)

        # 한글 폰트 로드
        try:
            font = ImageFont.truetype(FONT_PATH, 24)
        except IOError:
            print("Font not found. Using default font.")
            font = ImageFont.load_default()

        # 텍스트 색상과 위치 결정
        text_color = get_best_text_color(img)
        x, y = calculate_text_position(img, position_hint, final_message, font)

        # 텍스트를 이미지에 그리기
        draw = ImageDraw.Draw(img)
        draw.text((x, y), final_message, font=font, fill=text_color)

        # 이미지 저장
        img_path = os.path.join(STATIC_FOLDER, 'result.png')
        img.save(img_path)

        print(f"Image saved at: {img_path}")

        # 결과 반환
        return jsonify({'imageUrl': f'http://localhost:5000/static/result.png'}), 200

    except Exception as e:
        print(f"Error generating image: {e}")
        return jsonify({'error': str(e)}), 500

# 정적 파일 제공
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_FOLDER, filename)

# 서버 실행
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)