import cv2
import os
import datetime
import time
from ultralytics import YOLO
from db_helper import insert_log_async

model = YOLO('models/best.pt')
helmet_model = YOLO('models/helmet.pt')

REAL_NAMES = {0: "Motorcycle", 1: "Car", 2: "Bus", 3: "Truck"}
CLASS_COLORS = {
    "Motorcycle": (0, 165, 255),
    "Car": (255, 255, 0),
    "Bus": (0, 0, 255),
    "Truck": (255, 0, 255)
}

current_video_path = None
current_source_id = None
counted_ids = set()
traffic_stats = {"total_vehicles": 0,
                 "motorbike": 0, "car": 0, "truck": 0, "bus": 0,
                 "no_helmet": 0}
event_logs = []
track_history = {}
virtual_line = []
is_running = False


def set_virtual_line(x1, y1, x2, y2):
    global virtual_line, is_running
    virtual_line = [(x1, y1), (x2, y2)]
    is_running = True
    print(f"Đã cập nhật vạch mới: {virtual_line}")


def reset_ai_state(filepath, source_id=None):
    global current_video_path, current_source_id, counted_ids, traffic_stats, event_logs, track_history, virtual_line, is_running
    current_video_path = filepath
    current_source_id = source_id
    counted_ids.clear()
    event_logs.clear()
    track_history.clear()
    virtual_line = []
    is_running = False
    for key in traffic_stats:
        traffic_stats[key] = 0


def get_current_source_id():
    global current_source_id
    return current_source_id


def replay_video():
    global counted_ids, traffic_stats, event_logs, track_history, is_running

    counted_ids.clear()
    event_logs.clear()
    track_history.clear()
    for key in traffic_stats:
        traffic_stats[key] = 0

    is_running = True
    print("🔄 Đã reset số liệu, chuẩn bị Replay...")


def ccw(A, B, C):
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])


def intersect(A, B, C, D):
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)


def generate_frames():
    global current_video_path, traffic_stats, counted_ids, event_logs, track_history, virtual_line, is_running, current_source_id

    if not current_video_path or not os.path.exists(current_video_path):
        return

    cap = cv2.VideoCapture(current_video_path)

    success, first_frame = cap.read()
    if success:
        first_frame = cv2.resize(first_frame, (1020, 600))
        while not is_running:
            temp_frame = first_frame.copy()
            cv2.rectangle(temp_frame, (160, 250), (860, 320), (0, 0, 0), -1)
            cv2.putText(temp_frame, "HAY CLICK 2 DIEM DE VE VACH DEM XE!", (180, 300),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)

            ret, buffer = cv2.imencode('.jpg', temp_frame)
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.1)

    line_start, line_end = virtual_line[0], virtual_line[1]

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.resize(frame, (1020, 600))
        cv2.line(frame, line_start, line_end, (0, 255, 255), 3)

        results = model.track(frame, persist=True, conf=0.3,
                              tracker="bytetrack.yaml", device=0, half=True)

        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu()
            track_ids = results[0].boxes.id.int().cpu().tolist()
            class_ids = results[0].boxes.cls.int().cpu().tolist()
            confs = results[0].boxes.conf.cpu().tolist()

            for box, track_id, class_id, conf in zip(boxes, track_ids, class_ids, confs):
                x1, y1, x2, y2 = map(int, box)
                cx = (x1 + x2) // 2
                cy = y2

                class_id_int = int(class_id)
                class_name = REAL_NAMES.get(class_id_int, "Unknown")
                color = CLASS_COLORS.get(class_name, (0, 255, 0))
                label = f"{class_name} ID:{track_id} {int(conf*100)}%"

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

                prev_pt = track_history.get(track_id)
                current_pt = (cx, cy)

                if prev_pt is not None:
                    if intersect(prev_pt, current_pt, line_start, line_end):
                        if track_id not in counted_ids:
                            counted_ids.add(track_id)
                            traffic_stats["total_vehicles"] += 1
                            print(
                                f"[AI COUNT] 🟢 Vừa đếm: {class_name} (ID: {track_id}) | TỔNG SỐ XE: {traffic_stats['total_vehicles']}")

                            log_type = class_name

                            if class_name == "Motorcycle":
                                traffic_stats["motorbike"] += 1

                                if helmet_model is not None:
                                    h_img, w_img, _ = frame.shape
                                    crop_y1 = max(0, y1 - 50)
                                    crop_y2 = min(h_img, y2)
                                    crop_x1 = max(0, x1 - 10)
                                    crop_x2 = min(w_img, x2 + 10)

                                    motorcycle_crop = frame[crop_y1:crop_y2,
                                                            crop_x1:crop_x2]

                                    if motorcycle_crop.size > 0:
                                        h_results = helmet_model.predict(
                                            motorcycle_crop, conf=0.2, verbose=False)
                                        is_violation = False
                                        for h_box in h_results[0].boxes:
                                            h_name = helmet_model.names[int(
                                                h_box.cls[0])].lower()
                                            if "no" in h_name or "without" in h_name:
                                                is_violation = True
                                                break

                                        if is_violation:
                                            traffic_stats["no_helmet"] += 1
                                            log_type = "🚨 Không mũ"
                                            cv2.rectangle(
                                                frame, (x1, y1), (x2, y2), (0, 0, 255), 4)
                                            cv2.putText(
                                                frame, "VI PHAM!", (x1, y1 - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)

                            elif class_name == "Car":
                                traffic_stats["car"] += 1
                            elif class_name == "Truck":
                                traffic_stats["truck"] += 1
                            elif class_name == "Bus":
                                traffic_stats["bus"] += 1

                            time_ram = datetime.datetime.now().strftime("%H:%M:%S")
                            event_logs.insert(
                                0, {"id": track_id, "type": log_type, "time": time_ram})
                            if len(event_logs) > 50:
                                event_logs.pop()

                            time_sql = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                            insert_log_async(
                                track_id, log_type, time_sql, current_source_id)

                track_history[track_id] = current_pt

        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    cap.release()
