import cv2
import os
import datetime
import time
from ultralytics import YOLO
from db_helper import insert_log_async

# 1. LOAD MODEL
model = YOLO('models/best.pt')

# 2. ĐỊNH NGHĨA ÁNH XẠ
REAL_NAMES = {0: "Xe may", 1: "O to", 2: "Xe tai", 3: "Xe buyt"}
CLASS_COLORS = {"Xe may": (0, 165, 255), "O to": (
    255, 255, 0), "Xe tai": (255, 0, 255), "Xe buyt": (0, 0, 255)}

# 3. BIẾN TOÀN CÚC
current_video_path = None
counted_ids = set()
traffic_stats = {"total_vehicles": 0,
                 "motorbike": 0, "car": 0, "truck": 0, "bus": 0}
event_logs = []
track_history = {}
virtual_line = []
is_running = False  # <-- CỜ TRẠNG THÁI CHỜ VẼ VẠCH


def set_virtual_line(x1, y1, x2, y2):
    global virtual_line, is_running
    virtual_line = [(x1, y1), (x2, y2)]
    is_running = True  # <-- Người dùng vẽ xong 2 điểm, kích hoạt chạy video!
    print(f"Đã cập nhật vạch mới: {virtual_line}")


def reset_ai_state(filepath):
    global current_video_path, counted_ids, traffic_stats, event_logs, track_history, virtual_line, is_running
    current_video_path = filepath
    counted_ids.clear()
    event_logs.clear()
    track_history.clear()
    virtual_line = []
    is_running = False  # Khóa video, chờ vẽ vạch
    for key in traffic_stats:
        traffic_stats[key] = 0


def replay_video():
    global counted_ids, traffic_stats, event_logs, track_history, is_running

    counted_ids.clear()
    event_logs.clear()
    track_history.clear()
    for key in traffic_stats:
        traffic_stats[key] = 0

    # Bật cờ chạy luôn vì vạch đã được vẽ từ lần trước
    is_running = True
    print("🔄 Đã reset số liệu, chuẩn bị Replay...")

# === THUẬT TOÁN TOÁN HỌC: KIỂM TRA GIAO CẮT ĐOẠN THẲNG ===


def ccw(A, B, C):
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])


def intersect(A, B, C, D):
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)
# ============================================================


def generate_frames():
    global current_video_path, traffic_stats, counted_ids, event_logs, track_history, virtual_line, is_running

    if not current_video_path or not os.path.exists(current_video_path):
        return

    cap = cv2.VideoCapture(current_video_path)

    # --- PHASE 1: DỪNG Ở KHUNG HÌNH ĐẦU TIÊN CHỜ VẼ VẠCH ---
    success, first_frame = cap.read()
    if success:
        first_frame = cv2.resize(first_frame, (1020, 600))
        while not is_running:
            temp_frame = first_frame.copy()
            # Vẽ thông báo nhấp nháy hoặc mờ lên màn hình
            cv2.rectangle(temp_frame, (160, 250), (860, 320), (0, 0, 0), -1)
            cv2.putText(temp_frame, "HAY CLICK 2 DIEM DE VE VACH DEM XE!", (180, 300),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)

            ret, buffer = cv2.imencode('.jpg', temp_frame)
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.1)  # Tạm nghỉ để không ngốn CPU

    # --- PHASE 2: BẮT ĐẦU CHẠY HỆ THỐNG AI (ĐÃ XÓA FRAME SKIPPING) ---
    line_start, line_end = virtual_line[0], virtual_line[1]

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break  # Hết video

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

                # ================= LOGIC VECTOR CẮT =================
                prev_pt = track_history.get(track_id)
                current_pt = (cx, cy)

                if prev_pt is not None:
                    if intersect(prev_pt, current_pt, line_start, line_end):
                        if track_id not in counted_ids:
                            counted_ids.add(track_id)
                            traffic_stats["total_vehicles"] += 1

                            if class_name == "Xe may":
                                traffic_stats["motorbike"] += 1
                            elif class_name == "O to":
                                traffic_stats["car"] += 1
                            elif class_name == "Xe tai":
                                traffic_stats["truck"] += 1
                            elif class_name == "Xe buyt":
                                traffic_stats["bus"] += 1

                            # 1. Định dạng thời gian cho Array RAM (chỉ lấy Giờ:Phút:Giây)
                            time_ram = datetime.datetime.now().strftime("%H:%M:%S")
                            event_logs.insert(
                                0, {"id": track_id, "type": class_name, "time": time_ram})
                            if len(event_logs) > 50:
                                event_logs.pop()

                            # 2. ĐỊNH DẠNG THỜI GIAN CHUẨN SQL & LƯU VÀO DATABASE
                            time_sql = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            insert_log_async(track_id, class_name, time_sql)

                track_history[track_id] = current_pt

        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    cap.release()
