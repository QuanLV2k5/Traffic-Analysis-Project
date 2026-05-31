class TrafficDashboard {
    constructor() {
        this.charts = {};
        this.startRealtimeUpdates();
        this.bindEvents();
    }

    startRealtimeUpdates() {
        setInterval(async () => {
            await this.updateStats();
            await this.updateVehicleCount();
            await this.updateRealtimeEvents();
        }, 1000);
    }

    async updateStats() {
        try {
            const res = await fetch('http://localhost:5000/api/stats');
            const stats = await res.json();
            document.getElementById('totalVehicles').textContent = stats.total_vehicles.toLocaleString();
            document.getElementById('complianceRate').textContent = stats.compliance_rate;
            document.getElementById('helmetCompliance').textContent = stats.compliance_rate;
            document.getElementById('alertCount').textContent = stats.alerts;
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
                let color = "#00d4ff";
                let borderClass = "";

                if (e.type.includes("Motorcycle")) {
                    icon = "motorcycle";
                    if (e.type.includes("no helmet") || e.type.includes("Không mũ") || e.type.includes("no")) {
                        icon = "exclamation-triangle";
                        color = "#ff4757";
                        borderClass = "helmet-no";
                    }
                }
                else if (e.type === "Truck") icon = "truck";
                else if (e.type === "Bus") icon = "bus";

                return `
                <div class="detection-item ${borderClass}" style="animation: fadeIn 0.5s ease-out;">
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <i class="fas fa-${icon}" style="color: ${color};"></i>
                        <span style="color: ${color};"><strong>${e.type}</strong> (ID: ${e.id})</span>
                    </div>
                    <div style="color: #00ff00; font-size: 0.9em;">[${e.time}]</div>
                </div>
            `}).join('');
        } catch (e) { }
    }

    // ==========================================
    // HÀM VẼ 3 BIỂU ĐỒ TỪ DATABASE
    // ==========================================
    async loadAndDrawCharts() {
        try {
            const res = await fetch('http://localhost:5000/api/chart_data');
            const dbData = await res.json();

            if (!dbData.traffic_over_time || dbData.traffic_over_time.labels.length === 0) {
                alert("Đang phân tích, chưa có đủ dữ liệu biểu đồ. Hãy chờ xe chạy qua vạch rồi bấm lại!");
                return;
            }

            Chart.defaults.color = '#fff';

            // 1. Line Chart
            if (this.charts.traffic) this.charts.traffic.destroy();
            const ctxTraffic = document.getElementById('trafficChart').getContext('2d');
            this.charts.traffic = new Chart(ctxTraffic, {
                type: 'line',
                data: {
                    labels: dbData.traffic_over_time.labels,
                    datasets: [{
                        label: 'Số lượng xe theo từng phút',
                        data: dbData.traffic_over_time.data,
                        borderColor: '#00d4ff',
                        backgroundColor: 'rgba(0, 212, 255, 0.2)',
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            // 2. Doughnut Chart (Phân loại xe)
            if (this.charts.vehicleType) this.charts.vehicleType.destroy();
            const ctxVehicle = document.getElementById('vehicleTypeChart').getContext('2d');
            this.charts.vehicleType = new Chart(ctxVehicle, {
                type: 'doughnut',
                data: {
                    labels: ['Xe máy', 'Ô tô', 'Xe tải', 'Xe buýt'],
                    datasets: [{
                        data: [
                            dbData.vehicle_types.Motorcycle,
                            dbData.vehicle_types.Car,
                            dbData.vehicle_types.Truck,
                            dbData.vehicle_types.Bus
                        ],
                        backgroundColor: ['#00a8ff', '#fbc531', '#e84118', '#8c7ae6'],
                        borderWidth: 0
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            // 3. Pie Chart (Mũ bảo hiểm)
            if (this.charts.violation) this.charts.violation.destroy();
            const ctxViolation = document.getElementById('violationChart').getContext('2d');
            this.charts.violation = new Chart(ctxViolation, {
                type: 'pie',
                data: {
                    labels: ['Tuân thủ (Có mũ)', 'Vi phạm (Không mũ)'],
                    datasets: [{
                        data: [dbData.violations.Helmet, dbData.violations.No_Helmet],
                        backgroundColor: ['#4cd137', '#e84118'],
                        borderWidth: 0
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            console.log("Đã vẽ biểu đồ thành công!");

        } catch (e) {
            console.error("Lỗi vẽ biểu đồ:", e);
        }
    }


    bindEvents() {
        const overlayCanvas = document.getElementById('overlayCanvas');
        const ctx = overlayCanvas ? overlayCanvas.getContext('2d') : null;

        const resizeCanvas = () => {
            if (overlayCanvas) {
                overlayCanvas.width = overlayCanvas.clientWidth;
                overlayCanvas.height = overlayCanvas.clientHeight;
            }
        };
        window.addEventListener('resize', resizeCanvas);

        const uploadInput = document.getElementById('videoUpload');
        uploadInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            document.getElementById('waitingMessage').innerText = "Uploading & Initializing...";
            document.getElementById('waitingMessage').style.display = 'block';
            document.getElementById('videoStream').style.display = 'none';
            overlayCanvas.style.display = 'none';

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
                    overlayCanvas.style.display = 'block';
                    resizeCanvas();

                    videoStream.src = 'http://localhost:5000/video_feed?' + new Date().getTime();

                    // Reset Chart
                    Object.values(this.charts).forEach(chart => chart.destroy());
                    this.charts = {};
                }
            } catch (error) { console.error('Upload failed:', error); }
        });

        let clickPoints = [];
        let isDrawing = false;

        if (overlayCanvas) {
            overlayCanvas.addEventListener('mousemove', (e) => {
                if (!isDrawing || clickPoints.length !== 1) return;
                const rect = overlayCanvas.getBoundingClientRect();
                const currentX = e.clientX - rect.left;
                const currentY = e.clientY - rect.top;

                ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
                ctx.beginPath();
                ctx.arc(clickPoints[0].canvasX, clickPoints[0].canvasY, 6, 0, 2 * Math.PI);
                ctx.fillStyle = '#ff4757';
                ctx.fill();

                ctx.beginPath();
                ctx.moveTo(clickPoints[0].canvasX, clickPoints[0].canvasY);
                ctx.lineTo(currentX, currentY);
                ctx.strokeStyle = '#00d4ff';
                ctx.lineWidth = 3;
                ctx.setLineDash([8, 8]);
                ctx.stroke();
                ctx.setLineDash([]);
            });

            overlayCanvas.addEventListener('click', async (e) => {
                if (overlayCanvas.style.display === 'none') return;
                const rect = overlayCanvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;

                const scaleX = 1020 / rect.width;
                const scaleY = 600 / rect.height;
                const backendX = Math.round(x * scaleX);
                const backendY = Math.round(y * scaleY);

                clickPoints.push({ canvasX: x, canvasY: y, backendX, backendY });

                if (clickPoints.length === 1) {
                    isDrawing = true;
                    const msg = document.getElementById('waitingMessage');
                    msg.style.display = 'block';
                    msg.style.background = 'rgba(0,0,0,0.8)';
                    msg.innerText = `📍 Đã đặt điểm bắt đầu. Hãy rê chuột và click điểm kết thúc!`;
                    setTimeout(() => msg.style.display = 'none', 3000);
                }

                if (clickPoints.length === 2) {
                    isDrawing = false;
                    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

                    try {
                        await fetch('http://localhost:5000/api/set_line', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                x1: clickPoints[0].backendX, y1: clickPoints[0].backendY,
                                x2: clickPoints[1].backendX, y2: clickPoints[1].backendY
                            })
                        });
                        const msg = document.getElementById('waitingMessage');
                        msg.style.display = 'block';
                        msg.innerText = `✅ Đã vẽ vạch mới! Khởi động AI...`;
                        setTimeout(() => msg.style.display = 'none', 2000);
                    } catch (error) { console.error('Lỗi khi vẽ vạch:', error); }
                    clickPoints = [];
                }
            });
        }

        const replayBtn = document.getElementById('replayBtn');
        if (replayBtn) {
            replayBtn.addEventListener('click', async () => {
                try {
                    const res = await fetch('http://localhost:5000/api/replay', { method: 'POST' });
                    const data = await res.json();
                    if (data.success) {
                        Object.values(this.charts).forEach(chart => chart.destroy());
                        this.charts = {};
                        const videoStream = document.getElementById('videoStream');
                        videoStream.src = 'http://localhost:5000/video_feed?' + new Date().getTime();
                    }
                } catch (e) { }
            });
        }

        // =====================================
        // SỰ KIỆN CHO NÚT TỔNG KẾT VÀ TABS
        // =====================================
        const btnDrawChart = document.getElementById('btnDrawChart');
        if (btnDrawChart) {
            btnDrawChart.addEventListener('click', () => {
                // Nhảy về Tab Lưu lượng mặc định
                document.querySelector('.tab[data-tab="traffic"]').click();
                this.loadAndDrawCharts();
            });
        }

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