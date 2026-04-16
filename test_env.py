import torch
from ultralytics import YOLO

print("1. Kiem tra phien ban PyTorch:", torch.__version__)

if torch.cuda.is_available():
    print("2. GPU NVIDIA da duoc kich hoat!")
    print("   Ten Card Do Hoa:", torch.cuda.get_device_name(0))
else:
    print("2. Chua nhan GPU. Dang chay bang CPU (Can kiem tra lai Buoc 4).")

print("3. Kiem tra YOLO:", YOLO.__name__)