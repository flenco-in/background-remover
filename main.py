# main.py
from flask import Flask
from handlers import BackgroundRemovalHandler, ImageGenerationHandler

app = Flask(__name__)

@app.route('/remove-background', methods=['POST'])
def remove_background_api():
    return BackgroundRemovalHandler.handle_request()

@app.route('/generate-image', methods=['POST'])
def generate_image_api():
    return ImageGenerationHandler.handle_request()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)