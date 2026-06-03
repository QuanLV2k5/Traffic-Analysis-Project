import os
from flask import Flask, jsonify, request, Response, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename

from core_ai import generate_frames, reset_ai_state, traffic_stats, event_logs, set_virtual_line, replay_video, get_current_source_id
from db_helper import get_or_create_video_source, save_system_config, get_chart_statistics

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

    source_id = get_or_create_video_source(filename)

    reset_ai_state(filepath, source_id)

    return jsonify({"success": True, "message": "Video uploaded successfully"})


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/set_line', methods=['POST'])
def update_line():
    data = request.json
    x1, y1, x2, y2 = data['x1'], data['y1'], data['x2'], data['y2']

    set_virtual_line(x1, y1, x2, y2)

    source_id = get_current_source_id()
    if source_id:
        save_system_config(source_id, x1, y1, x2, y2)

    return jsonify({"success": True})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    total_motos = traffic_stats.get("motorbike", 0)
    no_helmet = traffic_stats.get("no_helmet", 0)

    if total_motos > 0:
        compliance_rate = round(
            ((total_motos - no_helmet) / total_motos) * 100, 1)
    else:
        compliance_rate = 100.0

    return jsonify({
        "total_vehicles": traffic_stats["total_vehicles"],
        "compliance_rate": f"{compliance_rate}%",
        "alerts": no_helmet,
        "avg_speed": "N/A"
    })


@app.route('/api/vehicles/count', methods=['GET'])
def vehicle_count():
    return jsonify({
        "motorbike": traffic_stats["motorbike"],
        "car": traffic_stats["car"],
        "truck": traffic_stats["truck"],
        "bus": traffic_stats["bus"],
        "total": traffic_stats["total_vehicles"]
    })


@app.route('/api/replay', methods=['POST'])
def trigger_replay():
    replay_video()
    return jsonify({"success": True, "message": "Đã reset AI, sẵn sàng replay"})


@app.route('/api/events', methods=['GET'])
def get_events():
    return jsonify(event_logs)


@app.route('/api/chart_data', methods=['GET'])
def get_chart_data():
    source_id = get_current_source_id()
    data = get_chart_statistics(source_id)
    return jsonify(data)


if __name__ == '__main__':
    print("🚀 Khởi động Backend AI Giám sát Giao thông...")
    app.run(debug=True, port=5000, use_reloader=False)
