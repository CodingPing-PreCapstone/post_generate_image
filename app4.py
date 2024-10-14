from flask import Flask, request, jsonify, send_from_directory
from PIL import Image, ImageDraw, ImageFont, ImageStat
import openai
import os
import requests
from io import BytesIO

app = Flask(__name__)
from flask_cors import CORS
CORS(app)

openai.api_key = '여기에 본인 api key 입력'

STATIC_FOLDER = os.path.join(os.getcwd(), 'static')
HTML_FOLDER = os.path.join(STATIC_FOLDER, 'html')
FONTS_FOLDER = os.path.join(os.getcwd(), 'fonts')
FONT_PATH = os.path.join(FONTS_FOLDER, 'NanumBrush.ttf')

if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

def translate_text(text, target_language):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Translate '{text}' to {target_language}"}]
    )
    return response.choices[0].message['content'].strip()

def generate_short_message(message):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"{message}. within 20 letters"}]
    )
    return response.choices[0].message['content'].strip()

def calculate_text_position(image, position_hint, text, font):
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

    return max(0, min(x, image.width - text_width)), max(0, min(y, image.height - text_height))

def wrap_text(text, font, max_width):
    """텍스트를 주어진 너비에 맞게 줄바꿈합니다."""
    lines = []
    words = text.split(' ')
    line = []

    for word in words:
        test_line = ' '.join(line + [word])
        width, _ = font.getbbox(test_line)[2:]

        if width <= max_width:
            line.append(word)
        else:
            lines.append(' '.join(line))
            line = [word]

    if line:
        lines.append(' '.join(line))

    return '\n'.join(lines)

@app.route('/generate', methods=['POST'])
def generate_image():
    try:
        data = request.json
        title = data.get('title', '제목 없음')
        message = data.get('message', '내용 없음')
        instruction = data.get('instruction', '')
        font_name = data.get('font', 'NanumBrush.ttf')
        text_color = data.get('textColor', 'black')
        border_color = data.get('borderColor', 'white')
        position = data.get('position', 'center')
        font_size = data.get('fontSize', 30)

        font_path = os.path.join(FONTS_FOLDER, font_name)

        translated_title = translate_text(title, "English")
        translated_message = translate_text(message, "English")
        translated_instruction = translate_text(instruction, "English")

        summarized_message = generate_short_message(translated_message)
        result_message = translate_text(summarized_message, "Korean")

        prompt = (
            f"Generate an artistic image focusing on the theme: {translated_title}. "
            f"No text, letters, or symbols should appear. {translated_instruction}."
        )

        dalle_response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="512x512"
        )

        image_url = dalle_response['data'][0]['url']
        image_response = requests.get(image_url)
        img = Image.open(BytesIO(image_response.content))

        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            font = ImageFont.load_default()

        # 텍스트를 이미지 경계 내에 맞게 줄바꿈 처리
        wrapped_message = wrap_text(result_message, font, img.width - 20)

        x, y = calculate_text_position(img, position, wrapped_message, font)

        draw = ImageDraw.Draw(img)

        # 텍스트 테두리 그리기
        for offset in [-1, 1]:
            draw.text((x + offset, y), wrapped_message, font=font, fill=border_color)
            draw.text((x, y + offset), wrapped_message, font=font, fill=border_color)

        # 텍스트 그리기
        draw.text((x, y), wrapped_message, font=font, fill=text_color)

        img_path = os.path.join(STATIC_FOLDER, 'result.png')
        img.save(img_path)

        return jsonify({'imageUrl': f'http://localhost:5000/static/result.png'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_FOLDER, filename)

@app.route('/')
def serve_index():
    return send_from_directory(HTML_FOLDER, 'index.html')

@app.route('/fonts/<path:filename>')
def serve_fonts(filename):
    return send_from_directory('fonts', filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
