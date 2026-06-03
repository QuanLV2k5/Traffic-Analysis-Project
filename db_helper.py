import pyodbc
import threading

CONN_STR = (
    r'DRIVER={ODBC Driver 17 for SQL Server};'
    r'SERVER=localhost;'
    r'DATABASE=TrafficMonitorDB;'
    r'Trusted_Connection=yes;'
)


def get_or_create_video_source(filename):
    """
    Kiểm tra xem video đã có trong bảng VideoSource chưa.
    Nếu chưa có thì thêm mới, nếu có rồi thì lấy source_id ra.
    """
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT source_id FROM VideoSource WHERE source_name = ?", (filename,))
        row = cursor.fetchone()

        if row:
            source_id = row[0]
            print(f"[DB] Video đã tồn tại, lấy source_id: {source_id}")
        else:
            cursor.execute("""
                INSERT INTO VideoSource (source_name, source_path, status) 
                OUTPUT INSERTED.source_id 
                VALUES (?, ?, 'Active')
            """, (filename, f"uploads/{filename}"))
            source_id = cursor.fetchone()[0]
            conn.commit()
            print(f"[DB] Đã tạo VideoSource mới, source_id: {source_id}")

        cursor.close()
        conn.close()
        return source_id
    except Exception as e:
        print(f"[DB ERROR] Lỗi get_or_create_video_source: {e}")
        return None


def save_system_config(source_id, x1, y1, x2, y2):
    """
    Lưu hoặc cập nhật tọa độ vạch đếm xe cho video này.
    Đảm bảo mỗi video chỉ có 1 vạch (không sinh ra dữ liệu rác).
    """
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT config_id FROM SystemConfig WHERE source_id = ?", (source_id,))
        row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE SystemConfig 
                SET line_start_x=?, line_start_y=?, line_end_x=?, line_end_y=? 
                WHERE source_id=?
            """, (x1, y1, x2, y2, source_id))
            print(f"[DB] Đã UPDATE vạch ảo mới cho source_id {source_id}")
        else:
            cursor.execute("""
                INSERT INTO SystemConfig (source_id, line_start_x, line_start_y, line_end_x, line_end_y)
                VALUES (?, ?, ?, ?, ?)
            """, (source_id, x1, y1, x2, y2))
            print(f"[DB] Đã INSERT vạch ảo mới cho source_id {source_id}")

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] Lỗi save_system_config: {e}")


def insert_log_async(track_id, log_string, record_time, source_id=None):
    """
    Xử lý chuỗi log_string (VD: "Car" hoặc "Motorcycle (no helmet)")
    để lưu chuẩn vào database.
    """
    vehicle_type = "Motorcycle" if "no helmet" in log_string or "helmet" in log_string else log_string
    is_violation = 1 if "no helmet" in log_string else 0
    violation_name = "Không mũ bảo hiểm" if is_violation == 1 else None

    def run_query():
        try:
            conn = pyodbc.connect(CONN_STR)
            cursor = conn.cursor()

            sql_query = """
                INSERT INTO VehicleLogs (TrackID, VehicleType, IsViolation, ViolationName, RecordTime, source_id) 
                VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor.execute(sql_query, (track_id, vehicle_type,
                           is_violation, violation_name, record_time, source_id))

            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[DB ERROR] Lỗi lưu CSDL: {e}")

    threading.Thread(target=run_query, daemon=True).start()


def get_chart_statistics(source_id):
    """
    Truy vấn Database để lấy dữ liệu vẽ 3 biểu đồ cho một video cụ thể.
    """
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()

        stats = {
            "traffic_over_time": {"labels": [], "data": []},
            "vehicle_types": {"Motorcycle": 0, "Car": 0, "Truck": 0, "Bus": 0},
            "violations": {"Helmet": 0, "No_Helmet": 0}
        }

        if source_id is None:
            return stats

        cursor.execute("""
            SELECT FORMAT(RecordTime, 'HH:mm') as TimeMinute, COUNT(TrackID) as CarCount
            FROM VehicleLogs
            WHERE source_id = ?
            GROUP BY FORMAT(RecordTime, 'HH:mm')
            ORDER BY TimeMinute
        """, (source_id,))
        for row in cursor.fetchall():
            stats["traffic_over_time"]["labels"].append(row[0])
            stats["traffic_over_time"]["data"].append(row[1])

        cursor.execute("""
            SELECT VehicleType, COUNT(TrackID) 
            FROM VehicleLogs 
            WHERE source_id = ? AND IsViolation = 0 
            GROUP BY VehicleType
        """, (source_id,))
        for row in cursor.fetchall():
            v_type = row[0]
            if v_type in stats["vehicle_types"]:
                stats["vehicle_types"][v_type] = row[1]

        cursor.execute("""
            SELECT COUNT(TrackID) 
            FROM VehicleLogs 
            WHERE source_id = ? AND IsViolation = 1
        """, (source_id,))
        no_helmet_count = cursor.fetchone()[0]
        stats["vehicle_types"]["Motorcycle"] += no_helmet_count

        stats["violations"]["No_Helmet"] = no_helmet_count
        stats["violations"]["Helmet"] = stats["vehicle_types"]["Motorcycle"] - \
            no_helmet_count

        cursor.close()
        conn.close()
        return stats
    except Exception as e:
        print(f"[DB ERROR] Lỗi get_chart_statistics: {e}")
        return {}
