from flask import Flask, request, jsonify, send_file
from cleaner.exif_cleaner import clean_metadata, analyze_metadata
import tempfile
import os

app = Flask(__name__)

@app.route('/clean', methods=['POST'])
def clean():
    if 'image' not in request.files:
        return jsonify({"error": "No image provided"}), 400
    
    file = request.files['image']
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        file.save(tmp.name)
        try:
            result = clean_metadata(tmp.name)
            return send_file(result['output'], as_attachment=True, download_name=f"cleaned_{file.filename}")
        finally:
            for f in [tmp.name, result.get('output')]:
                if os.path.exists(f):
                    os.unlink(f)

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'image' not in request.files:
        return jsonify({"error": "No image provided"}), 400
    file = request.files['image']
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        file.save(tmp.name)
        try:
            result = analyze_metadata(tmp.name)
            return jsonify(result)
        finally:
            os.unlink(tmp.name)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
