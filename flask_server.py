from flask import Flask, render_template_string, Response, jsonify
import socket
import threading
import json
import time

app = Flask(__name__)

# 全局变量用于存储最新检测结果和线程安全锁
latest_detections = []
last_udp_time = 0  # 上次收到UDP数据的时间戳
detections_lock = threading.Lock()

# 配置参数
UDP_IP = "0.0.0.0"  # 在所有接口上监听
UDP_PORT = 5000
SERVER_HOST = "0.0.0.0" # Flask 主机
SERVER_PORT = 5000

# HTML 模板 (简洁科研风格)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CropGuard - 实时检测</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', -apple-system, sans-serif;
        }

        body {
            background: #f8f9fa;
            color: #1a1a2e;
            min-height: 100vh;
            padding: 2rem;
        }

        .container {
            max-width: 720px;
            margin: 0 auto;
        }

        header {
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid #e2e8f0;
        }

        header h1 {
            font-size: 1.5rem;
            font-weight: 600;
            color: #1a1a2e;
            margin-bottom: 0.25rem;
        }

        header p {
            font-size: 0.875rem;
            color: #6b7280;
        }

        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            font-size: 0.875rem;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: #10b981;
        }

        .status-dot.offline {
            background-color: #ef4444;
        }

        .obj-count {
            color: #6b7280;
        }

        /* 表格样式 */
        .det-table {
            width: 100%;
            border-collapse: collapse;
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            overflow: hidden;
        }

        .det-table thead {
            background: #f1f5f9;
        }

        .det-table th {
            text-align: left;
            padding: 0.625rem 1rem;
            font-size: 0.75rem;
            font-weight: 600;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .det-table td {
            padding: 0.625rem 1rem;
            font-size: 0.875rem;
            border-top: 1px solid #f1f5f9;
        }

        .det-table tbody tr:hover {
            background: #f8fafc;
        }

        .label-cell {
            font-weight: 500;
            text-transform: capitalize;
        }

        .conf-bar-bg {
            width: 100%;
            max-width: 120px;
            height: 6px;
            background: #e2e8f0;
            border-radius: 3px;
            overflow: hidden;
        }

        .conf-bar {
            height: 100%;
            border-radius: 3px;
            background: #3b82f6;
            transition: width 0.2s ease;
        }

        .conf-text {
            font-variant-numeric: tabular-nums;
            color: #374151;
            min-width: 42px;
            text-align: right;
        }

        .conf-cell {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .empty-state {
            text-align: center;
            padding: 3rem 1rem;
            color: #9ca3af;
            font-size: 0.875rem;
        }

    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>CropGuard 实时检测</h1>
            <p>K230 YOLO11 · UDP 数据流</p>
        </header>

        <div class="status-bar">
            <div class="status-indicator">
                <div class="status-dot" id="conn-dot"></div>
                <span id="conn-text">等待数据...</span>
            </div>
            <div class="obj-count">
                检测目标: <strong id="obj-count">0</strong>
            </div>
        </div>

        <div id="detections-container">
            <div class="empty-state">等待 K230 设备连接...</div>
        </div>
    </div>

    <script>
        const container = document.getElementById('detections-container');
        const countEl = document.getElementById('obj-count');
        const dotEl = document.getElementById('conn-dot');
        const connText = document.getElementById('conn-text');

        let lastReceived = Date.now();

        setInterval(() => {
            if (Date.now() - lastReceived > 3000) {
                dotEl.classList.add('offline');
                connText.innerText = '未收到数据';
                connText.style.color = '#ef4444';
            } else {
                dotEl.classList.remove('offline');
                connText.innerText = '接收中';
                connText.style.color = '#10b981';
            }
        }, 1000);

        const evtSource = new EventSource("/stream");

        evtSource.onmessage = function(event) {
            lastReceived = Date.now();
            const detections = JSON.parse(event.data);

            countEl.innerText = detections.length;

            if (detections.length === 0) {
                container.innerHTML = '<div class="empty-state">当前无检测目标</div>';
                return;
            }

            let rows = '';
            detections.forEach((det, idx) => {
                const pct = Math.round(det.confidence * 100);
                rows += `
                    <tr>
                        <td>${idx + 1}</td>
                        <td class="label-cell">${det.label}</td>
                        <td>
                            <div class="conf-cell">
                                <div class="conf-bar-bg">
                                    <div class="conf-bar" style="width:${pct}%"></div>
                                </div>
                                <span class="conf-text">${pct}%</span>
                            </div>
                        </td>
                    </tr>`;
            });

            container.innerHTML = `
                <table class="det-table">
                    <thead>
                        <tr><th>#</th><th>类别</th><th>置信度</th></tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>`;
        };

        evtSource.onerror = function(err) {
            connText.innerText = '连接错误';
            dotEl.classList.add('offline');
        };
    </script>
</body>
</html>
"""

def udp_listener():
    """后台线程，用于监听来自 K230 的 UDP 数据包"""
    global latest_detections, last_udp_time
    
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
                last_udp_time = time.time()
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
        while True:
            with detections_lock:
                # 超过2秒没有收到UDP数据，自动清空结果
                if last_udp_time > 0 and time.time() - last_udp_time > 2:
                    current_data = []
                else:
                    current_data = latest_detections.copy()
            
            payload = json.dumps(current_data)
            yield f"data: {payload}\n\n"
            
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
