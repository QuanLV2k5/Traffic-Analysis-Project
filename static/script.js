class TrafficDashboard {
    constructor() {
        this.initCharts();
        this.startRealtimeUpdates();
        this.bindEvents();
    }

    startRealtimeUpdates() {
        // Cứ mỗi 1.5 giây sẽ gọi API một lần để cập nhật số liệu
        setInterval(async () => {
            await this.updateStats();
            await this.updateVehicleCount();
            await this.updateRealtimeEvents();
        }, 1500);
    }

    async updateStats() {
        try {
            const res = await fetch('http://localhost:5000/api/stats');
            const stats = await res.json();

            // 1. Cập nhật con số trên Header
            document.getElementById('totalVehicles').textContent = stats.total_vehicles.toLocaleString();

            // 2. Cập nhật Biểu đồ động
            if (this.trafficChart) {
                const now = new Date().toLocaleTimeString('vi-VN', { hour12: false });

                // Bơm dữ liệu mới vào biểu đồ
                this.trafficChart.data.labels.push(now);
                this.trafficChart.data.datasets[0].data.push(stats.total_vehicles);

                // Giữ cho biểu đồ chỉ hiển thị 15 mốc thời gian gần nhất (cuộn ngang)
                if (this.trafficChart.data.labels.length > 15) {
                    this.trafficChart.data.labels.shift();
                    this.trafficChart.data.datasets[0].data.shift();
                }

                this.trafficChart.update();
            }
        } catch (e) { }
    }

    async updateVehicleCount() {
        try {
            const res = await fetch('http://localhost:5000/api/vehicles/count');
            const data = await res.json();
            const breakdownHTML = `
                <div class="vehicle-item"><span>🏍️ Xe máy</span><strong>${data.motorbike}</strong></div>
                <div class="vehicle-item"><span>🚗 Ô tô</span><strong>${data.car}</strong></div>
                <div class="vehicle-item"><span>🚚 Xe tải</span><strong>${data.truck}</strong></div>
                <div class="vehicle-item"><span>🚌 Xe buýt</span><strong>${data.bus}</strong></div>
            `;
            document.getElementById('vehicleBreakdown').innerHTML = breakdownHTML;
        } catch (e) { }
    }

    async updateRealtimeEvents() {
        try {
            const res = await fetch('http://localhost:5000/api/events');
            const events = await res.json();
            const list = document.getElementById('detectionList');

            if (events.length === 0) {
                list.innerHTML = '<div style="padding: 20px; text-align: center; color: #aaa;">Đang chờ xe đi qua...</div>';
                return;
            }

            list.innerHTML = events.map(e => {
                let icon = "car";
                if (e.type === "Xe may") icon = "motorcycle";
                if (e.type === "Xe tai") icon = "truck";
                if (e.type === "Xe buyt") icon = "bus";

                return `
                <div class="detection-item" style="animation: fadeIn 0.5s ease-out;">
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <i class="fas fa-${icon}" style="color: #00d4ff;"></i>
                        <span><strong>${e.type}</strong> (ID: ${e.id})</span>
                    </div>
                    <div style="color: #00ff00; font-size: 0.9em;">[${e.time}]</div>
                </div>
            `}).join('');
        } catch (e) { }
    }

    initCharts() {
        const ctx = document.getElementById('trafficChart');
        this.trafficChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Tổng lượng xe',
                    data: [],
                    borderColor: '#00d4ff',
                    backgroundColor: 'rgba(0, 212, 255, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: 'white' } },
                    y: { ticks: { color: 'white' }, beginAtZero: true }
                },
                animation: { duration: 0 } // Tắt animation để tránh giật khi cuộn
            }
        });
    }

    bindEvents() {
        // 1. Upload Video
        const uploadInput = document.getElementById('videoUpload');
        uploadInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            document.getElementById('waitingMessage').innerText = "Uploading & Initializing...";
            document.getElementById('waitingMessage').style.display = 'block';
            document.getElementById('videoStream').style.display = 'none';

            const formData = new FormData();
            formData.append('video', file);

            try {
                const response = await fetch('http://localhost:5000/api/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();

                if (data.success) {
                    document.getElementById('waitingMessage').style.display = 'none';
                    const videoStream = document.getElementById('videoStream');
                    videoStream.style.display = 'block';
                    videoStream.src = 'http://localhost:5000/video_feed?' + new Date().getTime();

                    // Reset biểu đồ khi up video mới
                    if (this.trafficChart) {
                        this.trafficChart.data.labels = [];
                        this.trafficChart.data.datasets[0].data = [];
                        this.trafficChart.update();
                    }
                }
            } catch (error) { console.error('Upload failed:', error); }
        });

        // 2. Bắt sự kiện Click vẽ vạch trên Video
        const videoElement = document.getElementById('videoStream');
        let clickPoints = [];
        videoElement.addEventListener('click', async (e) => {
            if (videoElement.style.display === 'none') return;

            const rect = videoElement.getBoundingClientRect();
            const scaleX = 1020 / rect.width;
            const scaleY = 600 / rect.height;
            const x = Math.round((e.clientX - rect.left) * scaleX);
            const y = Math.round((e.clientY - rect.top) * scaleY);

            clickPoints.push({ x, y });

            if (clickPoints.length === 1) {
                const msg = document.getElementById('waitingMessage');
                msg.style.display = 'block';
                msg.style.background = 'rgba(0,0,0,0.8)';
                msg.innerText = `Đã chọn điểm 1: (${x}, ${y}). Hãy click điểm thứ 2!`;
                setTimeout(() => msg.style.display = 'none', 2000);
            }

            if (clickPoints.length === 2) {
                try {
                    await fetch('http://localhost:5000/api/set_line', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            x1: clickPoints[0].x, y1: clickPoints[0].y,
                            x2: clickPoints[1].x, y2: clickPoints[1].y
                        })
                    });
                    const msg = document.getElementById('waitingMessage');
                    msg.style.display = 'block';
                    msg.innerText = `✅ Đã vẽ vạch mới! Video bắt đầu chạy...`;
                    setTimeout(() => msg.style.display = 'none', 2000);
                } catch (error) { }
                clickPoints = [];
            }
        });

        // 3. Xử lý nút Replay
        const replayBtn = document.getElementById('replayBtn');
        if (replayBtn) {
            replayBtn.addEventListener('click', async () => {
                try {
                    const res = await fetch('http://localhost:5000/api/replay', { method: 'POST' });
                    const data = await res.json();
                    if (data.success) {
                        // Xóa sạch biểu đồ cũ
                        if (this.trafficChart) {
                            this.trafficChart.data.labels = [];
                            this.trafficChart.data.datasets[0].data = [];
                            this.trafficChart.update();
                        }
                        // Load lại luồng
                        const videoStream = document.getElementById('videoStream');
                        videoStream.src = 'http://localhost:5000/video_feed?' + new Date().getTime();
                    }
                } catch (e) { }
            });
        }

        // 4. Tab biểu đồ (Tránh bị dính sự kiện vào các nút khác)
        document.querySelectorAll('.tab').forEach(tab => {
            if (!tab.classList.contains('upload-btn') && tab.id !== 'replayBtn') {
                tab.onclick = (e) => {
                    const clickedTab = e.currentTarget;
                    document.querySelector('.tab.active:not(.upload-btn):not(#replayBtn)')?.classList.remove('active');
                    clickedTab.classList.add('active');

                    document.querySelectorAll('.chart').forEach(c => c.style.display = 'none');
                    const chartId = clickedTab.dataset.tab + 'Chart';
                    const chartElement = document.getElementById(chartId);
                    if (chartElement) chartElement.style.display = 'block';
                };
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => new TrafficDashboard());