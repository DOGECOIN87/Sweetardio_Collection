import os
import sys
from flask import Flask, render_template, jsonify, send_file
from generator import generate_random_combination, create_image
import io
from PIL import Image
import base64

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/generate', methods=['GET'])
def generate():
    try:
        layers, char_name = generate_random_combination()
        output_path = create_image(layers)
        
        # Read the generated image and convert to base64
        with open(output_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode()
        
        return jsonify({
            'success': True,
            'character': char_name,
            'image': f'data:image/png;base64,{img_data}',
            'output_path': output_path
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def stats():
    try:
        from generator import get_files, CHARACTERZ, SKINZ, EYEZ, MOUTHZ, STICKERZ, WHAT_ARE_THOSEZ, BACKGROUNDZ
        
        char_files = get_files(CHARACTERZ)
        base_names = set()
        for f in char_files:
            name = f.replace("before_skinz_", "").replace("after_skinz_", "").replace(".png", "")
            base_names.add(name)
        
        return jsonify({
            'characters': len(base_names),
            'backgrounds': len(get_files(BACKGROUNDZ)),
            'skins': len(get_files(SKINZ)),
            'eyes': len(get_files(EYEZ)),
            'mouths': len(get_files(MOUTHZ)),
            'stickers': len(get_files(STICKERZ)),
            'footwear': len(get_files(WHAT_ARE_THOSEZ))
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
