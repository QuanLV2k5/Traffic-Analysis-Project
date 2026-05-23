import pyodbc
import threading

CONN_STR = (
    r'DRIVER={ODBC Driver 17 for SQL Server};'
    r'SERVER=localhost;'  # <--- SỬA DÒNG NÀY
    r'DATABASE=TrafficMonitorDB;'
    r'Trusted_Connection=yes;'
)


def insert_log_async(track_id, vehicle_type, record_time):
    """
    Hàm này sẽ tạo một luồng (Thread) riêng biệt để chạy lệnh INSERT SQL.
    Giúp luồng chính (Video AI) không bị khựng lại chờ Database phản hồi.
    """
    def run_query():
        try:
            conn = pyodbc.connect(CONN_STR)
            cursor = conn.cursor()

            sql_query = """
                INSERT INTO VehicleLogs (TrackID, VehicleType, RecordTime) 
                VALUES (?, ?, ?)
            """
            cursor.execute(sql_query, (track_id, vehicle_type, record_time))

            conn.commit()
            cursor.close()
            conn.close()
            print(f"[DB] Đã lưu SQL: {vehicle_type} (ID: {track_id})")
        except Exception as e:
            print(f"[DB ERROR] Lỗi lưu CSDL: {e}")

    # Khởi chạy luồng phụ
    threading.Thread(target=run_query, daemon=True).start()
