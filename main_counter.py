import cv2
from ultralytics import YOLO
import tkinter as tk
from tkinter import filedialog
import numpy as np

# --- 1. GIAO DIỆN CHỌN FILE VIDEO ---
root = tk.Tk()
root.withdraw()
print("Vui lòng chọn một file video giao thông...")
video_path = filedialog.askopenfilename(
    title="Chọn file video",
    filetypes=[("Video files", "*.mp4 *.avi *.mkv")]
)

if not video_path:
    print("Chưa chọn video. Chương trình kết thúc.")
    exit()

# --- 2. KHỞI TẠO AI (Nâng cấp lên bản Small) ---
model = YOLO('yolov8m.pt')

cap = cv2.VideoCapture(video_path)

# Đọc khung hình đầu tiên để người dùng vẽ vạch
success, frame = cap.read()
if not success:
    print("Không thể đọc được video.")
    exit()

# --- 3. HÀM XỬ LÝ SỰ KIỆN CLICK CHUỘT ---
line_points = []
frame_copy = frame.copy()  # Tạo bản sao để vẽ nháp


def draw_line(event, x, y, flags, param):
    global line_points, frame_copy
    # Nếu người dùng click chuột trái
    if event == cv2.EVENT_LBUTTONDOWN:
        if len(line_points) < 2:
            line_points.append((x, y))
            # Vẽ một chấm đỏ tại nơi vừa click
            cv2.circle(frame_copy, (x, y), 5, (0, 0, 255), -1)

            # Nếu đã click đủ 2 điểm, nối lại thành đường thẳng màu vàng
            if len(line_points) == 2:
                cv2.line(frame_copy, line_points[0],
                         line_points[1], (0, 255, 255), 2)
                print(
                    f"Đã vẽ vạch từ {line_points[0]} đến {line_points[1]}. Nhấn ENTER để bắt đầu!")

            cv2.imshow("Ve Ranh Gioi Dem Xe", frame_copy)


# Hiển thị cửa sổ cho người dùng vẽ
cv2.imshow("Ve Ranh Gioi Dem Xe", frame_copy)
print("HƯỚNG DẪN: Click chuột 2 điểm trên ảnh để vẽ vạch đếm xe. Sau đó nhấn phím ENTER để chạy.")
cv2.setMouseCallback("Ve Ranh Gioi Dem Xe", draw_line)

# Đợi người dùng nhấn phím Enter (mã ASCII là 13)
while True:
    key = cv2.waitKey(1) & 0xFF
    if key == 13 and len(line_points) == 2:
        break
cv2.destroyWindow("Ve Ranh Gioi Dem Xe")

# --- 4. KHỞI TẠO BIẾN ĐẾM ---
counted_ids = []
car_count = 0
motorbike_count = 0
truck_count = 0

# Lấy 2 điểm ranh giới đã vẽ
line_start = line_points[0]
line_end = line_points[1]

# --- 5. VÒNG LẶP CHẠY HỆ THỐNG ---
print("Hệ thống đang chạy... Nhấn phím 'q' để thoát.")
while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    # Track với ngưỡng tin cậy thấp (conf=0.2) để bắt xe ở xa
    results = model.track(frame, classes=[
                          2, 3, 5, 7], persist=True, tracker="bytetrack.yaml", verbose=False, conf=0.2)

    if results[0].boxes is not None and results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        ids = results[0].boxes.id.cpu().numpy().astype(int)
        classes = results[0].boxes.cls.cpu().numpy().astype(int)

        for box, track_id, cls in zip(boxes, ids, classes):
            x1, y1, x2, y2 = map(int, box)

            # Lấy tọa độ tâm xe
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

            # --- Thuật toán kiểm tra giao cắt bằng Diện tích Tam Giác ---
            # Vì đường kẻ giờ là đường chéo bất kỳ, ta không so sánh y tĩnh nữa.
            # Ta tạo 1 vùng đệm (buffer) xung quanh đường thẳng để bắt xe.
            # Để đơn giản cho sinh viên, ở đây anh dùng cách so sánh tương đối tọa độ Y của điểm tâm
            # với phương trình đường thẳng tại tọa độ X tương ứng.

            # Tính phương trình đường thẳng y = mx + c (Tránh chia cho 0 nếu vẽ đường thẳng đứng)
            if line_end[0] != line_start[0]:
                m = (line_end[1] - line_start[1]) / \
                    (line_end[0] - line_start[0])
                c = line_start[1] - m * line_start[0]
                expected_y = m * cx + c
            else:
                expected_y = cy  # Bỏ qua nếu là đường thẳng đứng hoàn toàn

            # Kiểm tra xem xe có nằm trong giới hạn chiều ngang của vạch không
            min_x = min(line_start[0], line_end[0])
            max_x = max(line_start[0], line_end[0])

            offset = 10  # Tăng sai số vì xe có thể đi nhanh
            if min_x <= cx <= max_x and (expected_y - offset) <= cy <= (expected_y + offset):
                if track_id not in counted_ids:
                    counted_ids.append(track_id)

                    if cls == 2:
                        car_count += 1
                    elif cls == 3:
                        motorbike_count += 1
                    elif cls in [5, 7]:
                        truck_count += 1

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"ID:{track_id}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Vẽ lại đường kẻ ranh giới lên video lúc đang chạy
    cv2.line(frame, line_start, line_end, (0, 255, 255), 2)

    # Hiển thị bảng thống kê
    cv2.putText(frame, f"O To: {car_count}", (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(frame, f"Xe May: {motorbike_count}", (20, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(frame, f"Xe Tai/Bus: {truck_count}", (20, 130),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    cv2.imshow("He thong Giam sat Luu luong", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
