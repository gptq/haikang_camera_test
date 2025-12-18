#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海康工业相机完整测试脚本
测试 SDK 加载、相机连接、取图功能
"""

import os
import sys
import ctypes
from ctypes import cast, POINTER, memset, byref, sizeof

# 设置环境变量
os.environ.setdefault("MVCAM_SDK_PATH", "/opt/MVS")
os.environ.setdefault("MVCAM_COMMON_RUNENV", "/opt/MVS/lib")
current_ld = os.environ.get("LD_LIBRARY_PATH", "")
if "/opt/MVS/lib/aarch64" not in current_ld:
    os.environ["LD_LIBRARY_PATH"] = f"/opt/MVS/lib/aarch64:{current_ld}"

# 添加 MvImport 到 Python path
mvimport_path = "/opt/MVS/Samples/64/Python/MvImport"
if mvimport_path not in sys.path:
    sys.path.insert(0, mvimport_path)

# 导入海康 SDK
from MvCameraControl_class import MvCamera
from CameraParams_header import (
    MV_CC_DEVICE_INFO_LIST, MV_CC_DEVICE_INFO,
    MV_GIGE_DEVICE, MV_USB_DEVICE, MV_ACCESS_Exclusive,
    MV_FRAME_OUT_INFO_EX
)


def bytes_to_str(byte_array):
    """将 c_ubyte 数组转换为字符串"""
    try:
        return bytes(byte_array).decode('utf-8', errors='ignore').strip('\x00')
    except:
        return str(bytes(byte_array))


def ip_int_to_str(ip_int):
    """将整数 IP 转换为字符串"""
    return f"{(ip_int >> 24) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 8) & 0xFF}.{ip_int & 0xFF}"


def test_enumerate_cameras():
    """测试枚举相机"""
    print("\n[1] 枚举相机设备")
    
    device_list = MV_CC_DEVICE_INFO_LIST()
    tlayer_type = MV_GIGE_DEVICE | MV_USB_DEVICE
    
    ret = MvCamera.MV_CC_EnumDevices(tlayer_type, device_list)
    if ret != 0:
        print(f"    ✗ 枚举失败: 0x{ret:08X}")
        return None
    
    n_devices = device_list.nDeviceNum
    print(f"    ✓ 找到 {n_devices} 个设备")
    
    cameras = []
    for i in range(n_devices):
        dev_info = cast(device_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
        
        if dev_info.nTLayerType == MV_GIGE_DEVICE:
            gige_info = dev_info.SpecialInfo.stGigEInfo
            ip = ip_int_to_str(gige_info.nCurrentIp)
            model = bytes_to_str(gige_info.chModelName)
            serial = bytes_to_str(gige_info.chSerialNumber)
            manufacturer = bytes_to_str(gige_info.chManufacturerName)
            
            print(f"\n    设备 {i+1}:")
            print(f"        类型: GigE 网络相机")
            print(f"        IP: {ip}")
            print(f"        厂商: {manufacturer}")
            print(f"        型号: {model}")
            print(f"        序列号: {serial}")
            cameras.append({'type': 'gige', 'ip': ip, 'dev_info': dev_info})
        
        elif dev_info.nTLayerType == MV_USB_DEVICE:
            usb_info = dev_info.SpecialInfo.stUsb3VInfo
            model = bytes_to_str(usb_info.chModelName)
            serial = bytes_to_str(usb_info.chSerialNumber)
            manufacturer = bytes_to_str(usb_info.chManufacturerName)
            
            print(f"\n    设备 {i+1}:")
            print(f"        类型: USB3 相机")
            print(f"        厂商: {manufacturer}")
            print(f"        型号: {model}")
            print(f"        序列号: {serial}")
            cameras.append({'type': 'usb3', 'model': model, 'dev_info': dev_info})
    
    return cameras


def test_camera_connection(camera_info):
    """测试相机连接"""
    print("\n[2] 测试相机连接")
    
    cam = MvCamera()
    dev_info = camera_info['dev_info']
    
    # 创建设备句柄
    ret = cam.MV_CC_CreateHandle(dev_info)
    if ret != 0:
        print(f"    ✗ 创建句柄失败: 0x{ret:08X}")
        return None
    print("    ✓ 创建句柄成功")
    
    # 打开设备
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print(f"    ✗ 打开设备失败: 0x{ret:08X}")
        cam.MV_CC_DestroyHandle()
        return None
    print("    ✓ 打开设备成功")
    
    return cam


def test_grab_image(cam):
    """测试取图"""
    print("\n[3] 测试取图功能")
    
    # 开始取流
    ret = cam.MV_CC_StartGrabbing()
    if ret != 0:
        print(f"    ✗ 开始取流失败: 0x{ret:08X}")
        return False
    print("    ✓ 开始取流成功")
    
    # 获取一帧图像
    stFrameInfo = MV_FRAME_OUT_INFO_EX()
    memset(byref(stFrameInfo), 0, sizeof(stFrameInfo))
    
    buf_size = 1920 * 1200 * 3  # 预分配缓冲区
    pData = (ctypes.c_ubyte * buf_size)()
    
    print("    等待取图 (3秒超时)...")
    ret = cam.MV_CC_GetOneFrameTimeout(pData, buf_size, stFrameInfo, 3000)
    if ret == 0:
        print(f"    ✓ 取图成功!")
        print(f"        分辨率: {stFrameInfo.nWidth} x {stFrameInfo.nHeight}")
        print(f"        帧号: {stFrameInfo.nFrameNum}")
        print(f"        像素格式: 0x{stFrameInfo.enPixelType:08X}")
    else:
        print(f"    ✗ 取图失败: 0x{ret:08X}")
        print(f"        (可能相机未曝光或网络问题)")
    
    # 停止取流
    cam.MV_CC_StopGrabbing()
    print("    ✓ 停止取流")
    
    return ret == 0


def cleanup(cam):
    """清理资源"""
    print("\n[4] 清理资源")
    if cam:
        cam.MV_CC_CloseDevice()
        cam.MV_CC_DestroyHandle()
    print("    ✓ 资源已释放")


def main():
    """主函数"""
    print("=" * 60)
    print("海康工业相机 SDK 完整测试")
    print("=" * 60)
    print(f"\nPython 版本: {sys.version.split()[0]}")
    print(f"运行平台: {os.uname().sysname} {os.uname().machine}")
    
    cameras = test_enumerate_cameras()
    if not cameras:
        print("\n未检测到相机，请确保相机已连接")
        return
    
    # 连接第一个相机
    cam = test_camera_connection(cameras[0])
    if cam:
        test_grab_image(cam)
        cleanup(cam)
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
