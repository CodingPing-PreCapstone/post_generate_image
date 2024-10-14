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
openai.api_key = '여기에 키 입력'

# 'static' 폴더 생성
STATIC_FOLDER = 'static'
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

FONT_PATH = os.path.join(os.getcwd(), '/Users/syb/Downloads/post_generate_image-main/fonts/NanumMyeongjoExtraBold.ttf')

def translate_text(text, target_language):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Translate this to {target_language}: {text}"}]
    )
    return response.choices[0].message['content'].strip()

def summarize_message(text):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Summarize the following message briefly: {text}"}]
    )
    return response.choices[0].message['content'].strip()

def extract_keywords(text):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Extract important keywords from this message: {text}"}]
    )
    return response.choices[0].message['content'].strip()

def ask_gpt_for_text_position(image_description):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Suggest a text position for the following image: '{image_description}'"}]
    )
    return response.choices[0].message['content'].strip()

def get_best_text_and_border_color(image):
    stat = ImageStat.Stat(image)
    r, g, b = stat.mean[:3]
    brightness = (r * 0.299 + g * 0.587 + b * 0.114)
    return ('black', 'white') if brightness > 128 else ('white', 'black')

def adjust_font_size(draw, text, font_path, max_width, max_height):
    font_size = 24
    font = ImageFont.truetype(font_path, font_size)
    while True:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        if text_width <= max_width and text_height <= max_height:
            break
        font_size -= 1
        font = ImageFont.truetype(font_path, font_size)
    return font

def calculate_text_position(image, position_hint, text, font):
    """GPT가 제안한 위치에 따라 텍스트 좌표를 계산합니다."""
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    if position_hint == 'top left':
        x, y = 10, 10
    elif position_hint == 'top right':
        x, y = image.width - text_width - 10, 10
    elif position_hint == 'bottom right':
        x, y = image.width - text_width - 10, image.height - text_height - 10
    elif position_hint == 'bottom left':
        x, y = 10, image.height - text_height - 10
    else:
        x = (image.width - text_width) / 2
        y = (image.height - text_height) / 2

    x = max(0, min(x, image.width - text_width))
    y = max(0, min(y, image.height - text_height))
    return x, y

@app.route('/generate', methods=['POST'])
def generate_image():
    try:
        data = request.json
        title = data.get('title', '제목 없음')
        message = data.get('message', '내용 없음')
        instruction = data.get('instruction', '')

        translated_message = translate_text(message, "English")
        summarized_message = summarize_message(translated_message)
        final_message = translate_text(summarized_message, "Korean")

        keywords = extract_keywords(translated_message)
        translated_instruction = translate_text(instruction, "English")

        prompt = (
            f"Create an image based on the following keywords: {keywords}. "
            f"{translated_instruction}. Ensure the image contains no text."
        )

        dalle_response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="512x512"
        )

        image_url = dalle_response['data'][0]['url']
        image_response = requests.get(image_url)
        img = Image.open(BytesIO(image_response.content))

        position_hint = ask_gpt_for_text_position(translated_message)

        draw = ImageDraw.Draw(img)
        text_color, border_color = get_best_text_and_border_color(img)

        font = adjust_font_size(draw, final_message, FONT_PATH, img.width - 20, img.height - 20)

        x, y = calculate_text_position(img, position_hint, final_message, font)

        for offset in [-1, 1]:
            draw.text((x + offset, y), final_message, font=font, fill=border_color)
            draw.text((x, y + offset), final_message, font=font, fill=border_color)
        draw.text((x, y), final_message, font=font, fill=text_color)

        img_path = os.path.join(STATIC_FOLDER, 'result.png')
        img.save(img_path)

        return jsonify({'imageUrl': f'http://localhost:5000/static/result.png'}), 200

    except Exception as e:
        print(f"Error generating image: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_FOLDER, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)