from libs.PipeLine import PipeLine
from libs.YOLO import YOLO11
from libs.Utils import *
import os,sys,gc
import ulab.numpy as np
import image
import network
import usocket as socket
import json
import time

# WiFi配置（请修改这些参数）
WIFI_SSID = "ling"
WIFI_PASSWORD = "87654321"
SERVER_IP = "192.168.192.27" # Flask服务器的IP地址
SERVER_PORT = 5000

def connect_wifi(ssid, pwd):
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.connect(ssid, pwd)
    print("Connecting to WiFi...")
    timeout = 10
    start_time = time.time()
    while not sta.isconnected():
        if time.time() - start_time > timeout:
            print("WiFi connection timeout!")
            return False
        time.sleep(1)
    print("WiFi connected:", sta.ifconfig())
    return True

if __name__=="__main__":
    # 这里仅为示例，自定义场景请修改为您自己的模型路径、标签名称、模型输入大小
    kmodel_path="/fruit_det_yolo11n_320.kmodel"
    labels = ["apple","banana","orange"]
    model_input_size=[320,320]

    # 添加显示模式，默认hdmi，可选hdmi/lcd/lt9611/st7701/hx8399/nt35516,其中hdmi默认置为lt9611，分辨率1920*1080；lcd默认置为st7701，分辨率800*480
    display_mode="lcd"
    rgb888p_size=[640,360]
    confidence_threshold = 0.5
    nms_threshold=0.45
    # 初始化PipeLine
    pl=PipeLine(rgb888p_size=rgb888p_size,display_mode=display_mode)
    pl.create()
    display_size=pl.get_display_size()
    # 初始化YOLO11实例
    yolo=YOLO11(task_type="detect",
                mode="video",
                kmodel_path=kmodel_path,
                labels=labels,
                rgb888p_size=rgb888p_size,
                model_input_size=model_input_size,
                display_size=display_size,
                conf_thresh=confidence_threshold,
                nms_thresh=nms_threshold,
                max_boxes_num=50,
                debug_mode=0)
    yolo.config_preprocess()
    
    # 初始化网络
    udp_socket = None
    if connect_wifi(WIFI_SSID, WIFI_PASSWORD):
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print("UDP Socket ready, sending to {}:{}".format(SERVER_IP, SERVER_PORT))
    while True:
        with ScopedTiming("total",1):
            # 逐帧推理
            img=pl.get_frame()
            res=yolo.run(img)
            
            # 通过UDP发送结果
            if res and udp_socket:
                payload = []
                for det in res:
                    try:
                        # 提取类别和置信度，处理对象和元组/列表格式
                        c_id = det.classid if hasattr(det, 'classid') else (det[4] if type(det) in (list, tuple) and len(det) > 4 else 0)
                        conf = det.score if hasattr(det, 'score') else (det[5] if type(det) in (list, tuple) and len(det) > 5 else 0.0)
                        
                        label_name = labels[int(c_id)] if 0 <= int(c_id) < len(labels) else str(c_id)
                        payload.append({"label": label_name, "confidence": float(conf)})
                    except Exception as e:
                        pass
                
                if payload:
                    try:
                        msg = json.dumps(payload)
                        udp_socket.sendto(msg.encode('utf-8'), (SERVER_IP, SERVER_PORT))
                    except Exception as e:
                        print("UDP send error:", e)

            yolo.draw_result(res,pl.osd_img)
            pl.show_image()
            gc.collect()
    yolo.deinit()
    pl.destroy()
