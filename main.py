import os
from flask import Flask, jsonify, request, Response, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Import "Bộ não AI" từ file core_ai.py mà chúng ta vừa tạo
from core_ai import generate_frames, reset_ai_state, traffic_stats, event_logs, set_virtual_line, replay_video

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({"success": False, "error": "No video file provided"}), 400

    file = request.files['video']
    if file.filename == '':
        return jsonify({"success": False, "error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Đánh thức AI và reset bộ đếm
    reset_ai_state(filepath)

    return jsonify({"success": True, "message": "Video uploaded successfully"})


@app.route('/video_feed')
def video_feed():
    # Truyền luồng AI thẳng lên Frontend
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/set_line', methods=['POST'])
def update_line():
    data = request.json
    set_virtual_line(data['x1'], data['y1'], data['x2'], data['y2'])
    return jsonify({"success": True})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    # Trả số liệu ĐẾM THẬT (không dùng random nữa)
    return jsonify({
        "total_vehicles": traffic_stats["total_vehicles"],
        "compliance_rate": 100,  # Mock tạm thời cho Mũ bảo hiểm
        "avg_speed": "N/A"
    })


@app.route('/api/vehicles/count', methods=['GET'])
def vehicle_count():
    # Trả số liệu PHÂN LOẠI THẬT
    return jsonify({
        "motorbike": traffic_stats["motorbike"],
        "car": traffic_stats["car"],
        "truck": traffic_stats["truck"],
        "bus": traffic_stats["bus"],
        "total": traffic_stats["total_vehicles"]
    })


@app.route('/api/replay', methods=['POST'])
def trigger_replay():
    # Gọi hàm reset mềm ở core_ai
    replay_video()
    return jsonify({"success": True, "message": "Đã reset AI, sẵn sàng replay"})


@app.route('/api/events', methods=['GET'])
def get_events():
    return jsonify(event_logs)


if __name__ == '__main__':
    print("🚀 Khởi động Backend AI Giám sát Giao thông...")
    app.run(debug=True, port=5000, use_reloader=False)
