from flask import Flask, render_template_string, Response, jsonify
import socket
import threading
import json
import time

app = Flask(__name__)

# 全局变量用于存储最新检测结果和线程安全锁
latest_detections = []
detections_lock = threading.Lock()

# 配置参数
UDP_IP = "0.0.0.0"  # 在所有接口上监听
UDP_PORT = 5000
SERVER_HOST = "0.0.0.0" # Flask 主机
SERVER_PORT = 5000

# HTML 模板 (使用具有充满活力的颜色和动画的现代毛玻璃 UI)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>K230 YOLO Vision Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --text-main: #f8fafc;
            --text-accent: #38bdf8;
            --border-color: rgba(255, 255, 255, 0.1);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Outfit', sans-serif;
        }

        body {
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at top right, #1e1b4b, transparent 40%),
                              radial-gradient(circle at bottom left, #064e3b, transparent 40%);
            background-attachment: fixed;
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 2rem;
        }

        header {
            text-align: center;
            margin-bottom: 3rem;
            animation: fadeInDown 1s ease-out;
        }

        header h1 {
            font-size: 3rem;
            font-weight: 800;
            background: linear-gradient(to right, #38bdf8, #a78bfa, #f472b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
            letter-spacing: -1px;
        }

        header p {
            color: #94a3b8;
            font-size: 1.1rem;
        }

        .dashboard-container {
            width: 100%;
            max-width: 1000px;
            background: var(--card-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 2rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }

        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 2rem;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-weight: 600;
        }

        .pulse {
            width: 12px;
            height: 12px;
            background-color: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            animation: pulse-animation 2s infinite;
        }

        @keyframes pulse-animation {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        .detections-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1.5rem;
        }

        .det-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 1.5rem;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            animation: fadeIn 0.4s ease-out forwards;
            position: relative;
            overflow: hidden;
        }
        
        .det-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 4px;
            background: linear-gradient(90deg, #38bdf8, #818cf8);
        }

        .det-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
            background: rgba(255, 255, 255, 0.06);
        }

        .det-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }

        .det-label {
            font-size: 1.5rem;
            font-weight: 800;
            text-transform: capitalize;
            color: #f8fafc;
        }

        .det-conf-badge {
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
        }

        .progress-bg {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 99px;
            overflow: hidden;
            margin-top: 0.5rem;
        }

        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #38bdf8, #818cf8);
            border-radius: 99px;
            transition: width 0.3s ease;
        }

        .empty-state {
            grid-column: 1 / -1;
            text-align: center;
            padding: 4rem 2rem;
            color: #64748b;
        }

        .empty-state svg {
            width: 64px;
            height: 64px;
            margin-bottom: 1rem;
            opacity: 0.5;
        }

        @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: scale(0.95); }
            to { opacity: 1; transform: scale(1); }
        }

    </style>
</head>
<body>
    <header>
        <h1>K230 YOLO Vision Dashboard</h1>
        <p>Real-time Target Detections Over UDP</p>
    </header>

    <div class="dashboard-container">
        <div class="status-bar">
            <div class="status-indicator">
                <div class="pulse" id="conn-pulse"></div>
                <span id="conn-text">Waiting for Stream...</span>
            </div>
            <div style="color: #94a3b8; font-size: 0.9rem;">
                <span id="obj-count">0</span> Objects Detected
            </div>
        </div>

        <div class="detections-grid" id="detections-container">
            <!-- Detection Cards will be injected here -->
            <div class="empty-state">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                </svg>
                <h3>Waiting for Detections</h3>
                <p>Start the yolo11_det_video.py script on your K230</p>
            </div>
        </div>
    </div>

    <script>
        const container = document.getElementById('detections-container');
        const countEl = document.getElementById('obj-count');
        const pulseEl = document.getElementById('conn-pulse');
        const countText = document.getElementById('conn-text');
        
        let lastReceived = Date.now();

        // 定期检查连接状态
        setInterval(() => {
            if (Date.now() - lastReceived > 3000) {
                pulseEl.style.backgroundColor = '#ef4444';
                pulseEl.style.boxShadow = '0 0 0 0 rgba(239, 68, 68, 0.7)';
                countText.innerText = 'No Data Received';
                countText.style.color = '#ef4444';
            } else {
                pulseEl.style.backgroundColor = '#10b981';
                pulseEl.style.boxShadow = '';
                countText.innerText = 'Receiving Data';
                countText.style.color = '#10b981';
            }
        }, 1000);

        // 使用 Server-Sent Events (SSE) 进行实时更新
        const evtSource = new EventSource("/stream");
        
        evtSource.onmessage = function(event) {
            lastReceived = Date.now();
            const detections = JSON.parse(event.data);
            
            countEl.innerText = detections.length;
            
            if (detections.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                        </svg>
                        <h3>No targets in view</h3>
                    </div>`;
                return;
            }

            let html = '';
            detections.forEach((det, idx) => {
                const confPercent = Math.round(det.confidence * 100);
                
                // 基于置信度的颜色映射
                let progressColor = 'linear-gradient(90deg, #38bdf8, #818cf8)'; // 高置信度 (蓝/紫)
                if(confPercent < 60) progressColor = 'linear-gradient(90deg, #fbbf24, #f59e0b)'; // 中等置信度 (黄/橙)
                if(confPercent < 40) progressColor = 'linear-gradient(90deg, #ef4444, #f87171)'; // 低置信度 (红)

                html += `
                    <div class="det-card" style="animation-delay: ${idx * 0.05}s">
                        <div class="det-header">
                            <span class="det-label">${det.label}</span>
                            <span class="det-conf-badge">${confPercent}%</span>
                        </div>
                        <div class="progress-bg">
                            <div class="progress-bar" style="width: ${confPercent}%; background: ${progressColor};"></div>
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        };

        evtSource.onerror = function(err) {
            console.error("EventSource failed:", err);
            countText.innerText = 'Connection Error';
            pulseEl.style.backgroundColor = '#ef4444';
        };
    </script>
</body>
</html>
"""

def udp_listener():
    """后台线程，用于监听来自 K230 的 UDP 数据包"""
    global latest_detections
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"[*] UDP 服务器正在监听 {UDP_IP}:{UDP_PORT}")
    
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            payload = data.decode('utf-8')
            # 解析 JSON 数据载荷
            detections = json.loads(payload)
            
            # 更新全局状态
            with detections_lock:
                latest_detections = detections
                
        except json.JSONDecodeError:
            print("收到格式错误的 JSON:", data)
        except Exception as e:
            print("UDP 监听器错误:", e)

@app.route('/')
def index():
    """提供仪表板 UI"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/stream')
def stream():
    """Server-Sent Events 端点，用于将数据流式传输到前端"""
    def generate():
        last_sent = None
        while True:
            with detections_lock:
                current_data = latest_detections.copy()
            
            # 发送数据 (我们可以持续发送或者仅在数据变化时发送)
            # 我们序列化整个数组以便发送
            payload = json.dumps(current_data)
            yield f"data: {payload}\n\n"
            
            # 短暂进入睡眠以避免过度占用浏览器资源，并且大致匹配帧率
            time.sleep(0.1)

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    # 获取本地 IP 以便指导用户
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1"

    print("="*60)
    print(f"[*] 正在启动 K230 YOLO 仪表板服务器")
    print(f"[*] 请在 K230 的 `yolo11_det_video.py` 中设置 SERVER_IP = '{local_ip}'")
    print(f"[*] 请在浏览器中打开: http://{local_ip}:{SERVER_PORT}")
    print("="*60)
    
    # 启动 UDP 监听线程
    listener_thread = threading.Thread(target=udp_listener, daemon=True)
    listener_thread.start()
    
    # 启动 Flask 应用
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, threaded=True)
