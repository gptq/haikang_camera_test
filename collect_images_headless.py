#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海康工业相机 Headless 采集脚本 (增强版)
适用于无 GUI 的边缘设备 (RK3588 等)

功能:
- 自定义分辨率 (ROI 或 Resize)
- 硬触发模式 (外部信号触发)
- 软触发模式
- 连续采集模式
- 自动像素格式转换 (支持 Bayer12p 等)
"""

import os
import sys
import time
import ctypes
import argparse
from datetime import datetime
from ctypes import byref, sizeof, memset, POINTER, cast, c_void_p

# 设置环境
os.environ.setdefault("MVCAM_SDK_PATH", "/opt/MVS")
os.environ.setdefault("MVCAM_COMMON_RUNENV", "/opt/MVS/lib")
sys.path.insert(0, "/opt/MVS/Samples/64/Python/MvImport")

import numpy as np
import cv2

from MvCameraControl_class import MvCamera
from CameraParams_header import (
    MV_CC_DEVICE_INFO_LIST, MV_CC_DEVICE_INFO, MV_GIGE_DEVICE, MV_USB_DEVICE,
    MV_ACCESS_Exclusive, MV_FRAME_OUT_INFO_EX, MVCC_INTVALUE, MVCC_ENUMVALUE,
    MV_SAVE_IMAGE_PARAM_EX, MV_Image_Bmp, MV_Image_Jpeg
)
from PixelType_header import PixelType_Gvsp_BGR8_Packed


class HikrobotCamera:
    """海康相机封装类"""
    
    def __init__(self, camera_ip):
        self.camera_ip = camera_ip
        self.cam = None
        self.dev_info = None
        self.width = 0
        self.height = 0
        self.payload_size = 0
        self.pData = None
        self.pDataBGR = None
        self.stFrameInfo = None
        
    def connect(self):
        """连接相机"""
        self.dev_info = self._find_camera_by_ip(self.camera_ip)
        if self.dev_info is None:
            raise RuntimeError(f"未找到相机: {self.camera_ip}")
        
        self.cam = MvCamera()
        ret = self.cam.MV_CC_CreateHandle(self.dev_info)
        if ret != 0:
            raise RuntimeError(f"创建句柄失败: 0x{ret:08X}")
        
        ret = self.cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if ret != 0:
            self.cam.MV_CC_DestroyHandle()
            raise RuntimeError(f"打开设备失败: 0x{ret:08X}")
        
        # 获取当前尺寸
        stWidth = MVCC_INTVALUE()
        stHeight = MVCC_INTVALUE()
        stPayload = MVCC_INTVALUE()
        stPixel = MVCC_ENUMVALUE()
        
        self.cam.MV_CC_GetIntValue("Width", stWidth)
        self.cam.MV_CC_GetIntValue("Height", stHeight)
        self.cam.MV_CC_GetIntValue("PayloadSize", stPayload)
        self.cam.MV_CC_GetEnumValue("PixelFormat", stPixel)
        
        self.width = stWidth.nCurValue
        self.height = stHeight.nCurValue
        self.payload_size = stPayload.nCurValue
        self.pixel_format = stPixel.nCurValue
        
        print(f"相机连接成功: {self.camera_ip}")
        print(f"原始分辨率: {self.width} x {self.height}")
        print(f"原始像素格式: 0x{self.pixel_format:08X}")
        
        # 设置像素格式为 BayerRG8 (方便 OpenCV 处理)
        BAYER_RG8 = 0x01080009
        if self.pixel_format != BAYER_RG8:
            ret = self.cam.MV_CC_SetEnumValue("PixelFormat", BAYER_RG8)
            if ret == 0:
                self.pixel_format = BAYER_RG8
                # 更新 PayloadSize
                self.cam.MV_CC_GetIntValue("PayloadSize", stPayload)
                self.payload_size = stPayload.nCurValue
                print(f"像素格式已设置为 BayerRG8")
        
    def _find_camera_by_ip(self, camera_ip):
        """根据 IP 查找相机"""
        device_list = MV_CC_DEVICE_INFO_LIST()
        MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, device_list)
        
        for i in range(device_list.nDeviceNum):
            dev_info = cast(device_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if dev_info.nTLayerType == MV_GIGE_DEVICE:
                ip_int = dev_info.SpecialInfo.stGigEInfo.nCurrentIp
                ip = f"{(ip_int>>24)&0xFF}.{(ip_int>>16)&0xFF}.{(ip_int>>8)&0xFF}.{ip_int&0xFF}"
                if ip == camera_ip:
                    return dev_info
        return None
    
    def set_roi(self, width, height, offset_x=None, offset_y=None):
        """设置 ROI 区域 (相机端裁剪)"""
        orig_w, orig_h = self.width, self.height
        
        # 如果未指定偏移，则居中
        if offset_x is None:
            offset_x = (orig_w - width) // 2
        if offset_y is None:
            offset_y = (orig_h - height) // 2
        
        # 确保偏移量为有效值
        offset_x = max(0, min(offset_x, orig_w - width))
        offset_y = max(0, min(offset_y, orig_h - height))
        
        # 设置 ROI
        self.cam.MV_CC_SetIntValue("Width", width)
        self.cam.MV_CC_SetIntValue("Height", height)
        self.cam.MV_CC_SetIntValue("OffsetX", offset_x)
        self.cam.MV_CC_SetIntValue("OffsetY", offset_y)
        
        # 更新 payload size
        stPayload = MVCC_INTVALUE()
        self.cam.MV_CC_GetIntValue("PayloadSize", stPayload)
        self.payload_size = stPayload.nCurValue
        
        self.width = width
        self.height = height
        print(f"ROI 设置: {width}x{height} @ ({offset_x}, {offset_y})")
    
    def set_trigger_mode(self, mode):
        """
        设置触发模式
        mode: 'continuous' | 'software' | 'hardware'
        """
        if mode == 'continuous':
            # 连续采集模式 (自由运行)
            self.cam.MV_CC_SetEnumValue("TriggerMode", 0)  # Off
            print("触发模式: 连续采集")
            
        elif mode == 'software':
            # 软触发模式
            self.cam.MV_CC_SetEnumValue("TriggerMode", 1)  # On
            self.cam.MV_CC_SetEnumValue("TriggerSource", 7)  # Software
            print("触发模式: 软触发")
            
        elif mode == 'hardware':
            # 硬触发模式 (Line0 输入)
            self.cam.MV_CC_SetEnumValue("TriggerMode", 1)  # On
            self.cam.MV_CC_SetEnumValue("TriggerSource", 0)  # Line0
            # 可选: 设置触发边沿
            self.cam.MV_CC_SetEnumValue("TriggerActivation", 0)  # RisingEdge
            print("触发模式: 硬触发 (Line0 上升沿)")
        else:
            raise ValueError(f"未知触发模式: {mode}")
    
    def set_exposure(self, exposure_us):
        """设置曝光时间 (微秒)"""
        self.cam.MV_CC_SetFloatValue("ExposureTime", float(exposure_us))
        print(f"曝光时间: {exposure_us} μs")
    
    def set_gain(self, gain_db):
        """设置增益 (dB)"""
        self.cam.MV_CC_SetFloatValue("Gain", float(gain_db))
        print(f"增益: {gain_db} dB")
    
    def start_grabbing(self):
        """开始取流"""
        # 分配原始数据缓冲区
        self.pData = (ctypes.c_ubyte * self.payload_size)()
        # 分配 BGR 转换后的缓冲区
        self.pDataBGR = (ctypes.c_ubyte * (self.width * self.height * 3))()
        self.stFrameInfo = MV_FRAME_OUT_INFO_EX()
        
        ret = self.cam.MV_CC_StartGrabbing()
        if ret != 0:
            raise RuntimeError(f"开始取流失败: 0x{ret:08X}")
        print("开始取流")
    
    def software_trigger(self):
        """发送软触发命令"""
        ret = self.cam.MV_CC_SetCommandValue("TriggerSoftware")
        return ret == 0
    
    def get_frame(self, timeout_ms=3000):
        """获取一帧图像 (自动转换为 BGR)"""
        memset(byref(self.stFrameInfo), 0, sizeof(self.stFrameInfo))
        ret = self.cam.MV_CC_GetOneFrameTimeout(
            self.pData, self.payload_size, self.stFrameInfo, timeout_ms
        )
        
        if ret != 0:
            return None
        
        h, w = self.stFrameInfo.nHeight, self.stFrameInfo.nWidth
        pixel_type = self.stFrameInfo.enPixelType
        
        # BayerRG8 格式处理
        if pixel_type == 0x01080009:  # BayerRG8
            data = np.frombuffer(self.pData, dtype=np.uint8, count=h*w).reshape((h, w))
            bgr = cv2.cvtColor(data, cv2.COLOR_BAYER_RG2BGR)
            return bgr
        
        # 其他 Bayer 格式
        elif pixel_type in [0x0110000D, 0x010C0027, 0x01100011, 0x010C002B]:
            # Bayer10/12 格式，需要先转为 8bit
            print(f"警告: 像素格式 0x{pixel_type:08X} 需要降位转换")
            # 按 16bit 读取再右移
            data16 = np.ctypeslib.as_array(self.pData[:h*w*2]).view(np.uint16).reshape((h, w))
            data8 = (data16 >> 4).astype(np.uint8)  # 12bit -> 8bit
            bgr = cv2.cvtColor(data8, cv2.COLOR_BAYER_RG2BGR)
            return bgr
        
        # Mono8
        elif pixel_type == 0x01080001:
            data = np.ctypeslib.as_array(self.pData[:h*w]).reshape((h, w))
            bgr = cv2.cvtColor(data, cv2.COLOR_GRAY2BGR)
            return bgr
        
        # BGR8
        elif pixel_type == 0x02180014:
            data = np.ctypeslib.as_array(self.pData[:h*w*3]).reshape((h, w, 3))
            return data.copy()
        
        else:
            print(f"未知像素格式: 0x{pixel_type:08X}")
            return None
    
    def stop_grabbing(self):
        """停止取流"""
        if self.cam:
            self.cam.MV_CC_StopGrabbing()
    
    def disconnect(self):
        """断开相机"""
        if self.cam:
            self.cam.MV_CC_CloseDevice()
            self.cam.MV_CC_DestroyHandle()
            self.cam = None
        print("相机已断开")
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, *args):
        self.stop_grabbing()
        self.disconnect()


# 定义像素格式转换结构体
class MV_CC_PIXEL_CONVERT_PARAM(ctypes.Structure):
    _fields_ = [
        ("nWidth", ctypes.c_uint),
        ("nHeight", ctypes.c_uint),
        ("enSrcPixelType", ctypes.c_uint),
        ("pSrcData", ctypes.POINTER(ctypes.c_ubyte)),
        ("nSrcDataLen", ctypes.c_uint),
        ("enDstPixelType", ctypes.c_uint),
        ("pDstBuffer", ctypes.POINTER(ctypes.c_ubyte)),
        ("nDstBufferSize", ctypes.c_uint),
        ("nDstLen", ctypes.c_uint),
    ]


def collect_images(args):
    """采集图像主函数"""
    
    with HikrobotCamera(args.ip) as cam:
        # 设置 ROI (如果指定了尺寸)
        if args.size:
            w, h = map(int, args.size.split('x'))
            cam.set_roi(w, h)
        
        # 设置触发模式
        cam.set_trigger_mode(args.trigger)
        
        # 设置曝光和增益 (可选)
        if args.exposure:
            cam.set_exposure(args.exposure)
        if args.gain:
            cam.set_gain(args.gain)
        
        # 开始采集
        cam.start_grabbing()
        
        os.makedirs(args.output, exist_ok=True)
        print(f"输出目录: {args.output}")
        print(f"采集参数: {args.count} 张")
        print("-" * 40)
        
        saved_count = 0
        for i in range(args.count):
            # 软触发模式需要发送触发命令
            if args.trigger == 'software':
                cam.software_trigger()
            
            # 硬触发模式会等待外部信号
            if args.trigger == 'hardware':
                print(f"[{i+1}/{args.count}] 等待硬触发信号...")
            
            frame = cam.get_frame(timeout_ms=args.timeout)
            
            if frame is not None:
                # Resize (如果需要)
                if args.resize:
                    rw, rh = map(int, args.resize.split('x'))
                    frame = cv2.resize(frame, (rw, rh), interpolation=cv2.INTER_LINEAR)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                filename = f"{args.prefix}_{i:04d}_{timestamp}.jpg"
                filepath = os.path.join(args.output, filename)
                cv2.imwrite(filepath, frame)
                print(f"[{i+1}/{args.count}] 保存: {filename} ({frame.shape[1]}x{frame.shape[0]})")
                saved_count += 1
            else:
                print(f"[{i+1}/{args.count}] 取图超时")
            
            if i < args.count - 1 and args.trigger == 'continuous':
                time.sleep(args.interval)
        
        print("-" * 40)
        print(f"采集完成！成功 {saved_count}/{args.count} 张")


def main():
    parser = argparse.ArgumentParser(
        description="海康相机 Headless 采集工具 (支持触发模式和自定义分辨率)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 连续采集 10 张，resize 到 640x640
  python %(prog)s --count 10 --resize 640x640

  # 使用 ROI 裁剪 640x640 (相机端)
  python %(prog)s --size 640x640 --count 5

  # 硬触发模式 (等待外部信号)
  python %(prog)s --trigger hardware --count 100

  # 软触发模式，自定义曝光
  python %(prog)s --trigger software --exposure 10000 --count 20
"""
    )
    
    parser.add_argument("--ip", default="192.168.2.124", help="相机 IP 地址")
    parser.add_argument("--output", "-o", default="./captured_images", help="输出目录")
    parser.add_argument("--count", "-n", type=int, default=10, help="采集张数")
    parser.add_argument("--interval", "-i", type=float, default=1.0, help="连续模式采集间隔(秒)")
    parser.add_argument("--prefix", "-p", default="img", help="文件名前缀")
    
    # 分辨率设置
    parser.add_argument("--size", "-s", help="相机 ROI 尺寸, 如 640x640 (相机端裁剪)")
    parser.add_argument("--resize", "-r", help="采集后 resize 尺寸, 如 640x640 (软件缩放)")
    
    # 触发模式
    parser.add_argument("--trigger", "-t", choices=['continuous', 'software', 'hardware'],
                        default='continuous', help="触发模式: continuous/software/hardware")
    parser.add_argument("--timeout", type=int, default=5000, help="取图超时(ms), 硬触发建议设大")
    
    # 相机参数
    parser.add_argument("--exposure", "-e", type=float, help="曝光时间(μs)")
    parser.add_argument("--gain", "-g", type=float, help="增益(dB)")
    
    args = parser.parse_args()
    collect_images(args)


if __name__ == "__main__":
    main()
