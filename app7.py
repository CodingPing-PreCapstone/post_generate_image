#11/13 이미지 jpg 설정 및 모든 이미지가 300kb 넘지는 않되, 가깝게 조정
from flask import Flask, request, jsonify, send_from_directory
from PIL import Image, ImageDraw, ImageFont
import openai
import os
import requests
from io import BytesIO
import concurrent.futures

app = Flask(__name__)
from flask_cors import CORS
CORS(app)  # CORS 설정을 통해 외부 도메인에서 API에 접근 가능하도록 허용

# OpenAI API 키 설정
openai.api_key = ''

# 정적 파일, HTML 파일, 폰트 경로 설정
STATIC_FOLDER = os.path.join(os.getcwd(), 'static')
HTML_FOLDER = os.path.join(STATIC_FOLDER, 'html')
REACT_FOLDER = os.path.join(STATIC_FOLDER, 'react')  # React 빌드 파일 경로 11/17
FONTS_FOLDER = os.path.join(os.getcwd(), 'fonts')
FONT_PATH = os.path.join(FONTS_FOLDER, 'NanumBrush.ttf')

# 정적 폴더가 없는 경우 생성
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

if not os.path.exists(REACT_FOLDER):  # React 폴더가 없는 경우 경고 출력 11/17
    print("⚠️ React build 폴더가 없습니다. React 빌드 파일을 static/react에 배치하세요.")

# 메시지를 짧게 요약하는 함수
def generate_short_message(message):
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": f"{message}. within 20 letters"}]
    )
    return response.choices[0].message['content'].strip()

# 텍스트 위치를 계산하는 함수
def calculate_text_position(image, position_hint, text, font):
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # 위치에 따라 x, y 좌표 계산
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

    # 텍스트가 이미지 밖으로 나가지 않도록 조정
    return max(0, min(x, image.width - text_width)), max(0, min(y, image.height - text_height))

# 텍스트를 주어진 너비에 맞게 줄바꿈하는 함수
def wrap_text(text, font, max_width):
    lines = []
    words = text.split(' ')
    line = []

    for word in words:
        test_line = ' '.join(line + [word])
        width, _ = font.getbbox(test_line)[2:]

        # 텍스트의 너비가 최대 너비를 초과할 경우 줄바꿈
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
        font_size = data.get('fontSize', 50)
        painting_style = data.get('painting_style', '선택 안함')

       # 메시지 요약 생성
        summarized_message = generate_short_message(message)
        print("summarized_message: " + summarized_message + "\n")
        result_message = summarized_message
        print("result_message: " + result_message + "\n")

        # 폰트 파일 경로 설정
        font_path = os.path.join(FONTS_FOLDER, font_name)

        # 메시지 요약 생성
        summarized_message = generate_short_message(message)

        # DALL·E에 이미지 생성을 요청하는 프롬프트 생성
        prompt = (
            f"Create an artistic image in the style of {painting_style}. "
            f"The theme is: {title}. "
            f"Exclude all text, letters, and symbols. Follow these additional instructions: {instruction}"
        )

        # DALL·E API를 통해 이미지 생성
        dalle_response = openai.Image.create(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )

        # DALL·E가 반환한 이미지 URL로부터 이미지 다운로드
        image_url = dalle_response['data'][0]['url']
        image_response = requests.get(image_url)
        img = Image.open(BytesIO(image_response.content))

        # 이미지 파일 크기를 조정하는 함수
        def save_image_with_compression(image, path, max_size):
            quality = 95  # JPEG 품질 초기 설정
            while quality > 10:
                with BytesIO() as buf:
                    image.save(buf, 'JPEG', quality=quality)
                    size = buf.tell()
                    if size <= max_size:
                        with open(path, 'wb') as f:
                            f.write(buf.getvalue())
                        print(f"Saved '{path}' with size {size / 1024:.2f} KB (Quality: {quality})")
                        break
                    quality -= 5  # 품질을 점진적으로 낮춤

        # 기본 생성 이미지를 저장 (텍스트가 없는 원본 이미지)
        original_img_path = os.path.join(STATIC_FOLDER, 'original.jpg')
        save_image_with_compression(img, original_img_path, 300 * 1024)  # 300KB 제한 적용, format='JPEG' 추가 

    
        # 폰트를 불러옴 (기본 폰트로 대체 가능)
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            font = ImageFont.load_default()

        # 텍스트 줄바꿈 처리
        wrapped_message = wrap_text(summarized_message, font, img.width - 20)

        # 텍스트 위치 계산
        x, y = calculate_text_position(img, position, wrapped_message, font)

        draw = ImageDraw.Draw(img)

        # 텍스트 테두리 그리기
        for offset in [-1, 1]:
            draw.text((x + offset, y), wrapped_message, font=font, fill=border_color)
            draw.text((x, y + offset), wrapped_message, font=font, fill=border_color)

        # 텍스트 그리기
        draw.text((x, y), wrapped_message, font=font, fill=text_color)

        # 텍스트가 추가된 이미지를 로컬에 저장 (최종 이미지)
        result_img_path = os.path.join(STATIC_FOLDER, 'result.jpg')
        save_image_with_compression(img, result_img_path, 300 * 1024)  # 300KB 제한 적용

        # 화면에는 result.jpg의 URL만 반환
        return jsonify({'imageUrl': f'http://localhost:5000/static/result.jpg'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# React 정적 파일 제공 라우트 추가 11/17
@app.route('/react')
def serve_react():
    return send_from_directory(os.path.join(STATIC_FOLDER, 'react'), 'index.html')

@app.route('/react/<path:filename>')
def serve_react_static(filename):
    return send_from_directory(os.path.join(STATIC_FOLDER, 'react'), filename)

# 정적 파일 제공
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_FOLDER, filename)

# HTML 파일 제공
@app.route('/')
def serve_index():
    return send_from_directory(HTML_FOLDER, 'index.html')

# 폰트 파일 제공
@app.route('/fonts/<path:filename>')
def serve_fonts(filename):
    return send_from_directory('fonts', filename)

# Flask 앱 실행
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)