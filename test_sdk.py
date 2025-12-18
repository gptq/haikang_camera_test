#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海康工业相机 SDK 测试脚本
测试 SDK 库加载和相机枚举功能
"""

import ctypes
import os
import sys

# SDK 路径配置
SDK_PATH = "/opt/MVS"
LIB_PATH = f"{SDK_PATH}/lib/aarch64"

# 传输层类型定义
MV_GIGE_DEVICE = 0x00000001
MV_1394_DEVICE = 0x00000002
MV_USB_DEVICE = 0x00000004
MV_CAMERALINK_DEVICE = 0x00000008

MV_MAX_DEVICE_NUM = 256

# GigE 设备信息结构
class MV_GIGE_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("nIpCfgOption", ctypes.c_uint),
        ("nIpCfgCurrent", ctypes.c_uint),
        ("nCurrentIp", ctypes.c_uint),
        ("nCurrentSubNetMask", ctypes.c_uint),
        ("nDefultGateWay", ctypes.c_uint),
        ("chManufacturerName", ctypes.c_char * 32),
        ("chModelName", ctypes.c_char * 32),
        ("chDeviceVersion", ctypes.c_char * 32),
        ("chManufacturerSpecificInfo", ctypes.c_char * 48),
        ("chSerialNumber", ctypes.c_char * 16),
        ("chUserDefinedName", ctypes.c_char * 16),
        ("nNetExport", ctypes.c_uint),
        ("nReserved", ctypes.c_uint * 4),
    ]

# USB3 设备信息结构
class MV_USB3_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("CrtlInEndPoint", ctypes.c_ubyte),
        ("CrtlOutEndPoint", ctypes.c_ubyte),
        ("StreamEndPoint", ctypes.c_ubyte),
        ("EventEndPoint", ctypes.c_ubyte),
        ("idVendor", ctypes.c_ushort),
        ("idProduct", ctypes.c_ushort),
        ("nDeviceNumber", ctypes.c_uint),
        ("chDeviceGUID", ctypes.c_char * 64),
        ("chVendorName", ctypes.c_char * 64),
        ("chModelName", ctypes.c_char * 64),
        ("chFamilyName", ctypes.c_char * 64),
        ("chDeviceVersion", ctypes.c_char * 64),
        ("chManufacturerName", ctypes.c_char * 64),
        ("chSerialNumber", ctypes.c_char * 64),
        ("chUserDefinedName", ctypes.c_char * 64),
        ("nbcdUSB", ctypes.c_uint),
        ("nDeviceAddress", ctypes.c_uint),
        ("nReserved", ctypes.c_uint * 2),
    ]

# 设备特殊信息联合体
class MV_CC_DEVICE_INFO_UNION(ctypes.Union):
    _fields_ = [
        ("stGigEInfo", MV_GIGE_DEVICE_INFO),
        ("stUsb3VInfo", MV_USB3_DEVICE_INFO),
        ("nReserved", ctypes.c_uint * 140),
    ]

# 设备信息结构
class MV_CC_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("nMajorVer", ctypes.c_ushort),
        ("nMinorVer", ctypes.c_ushort),
        ("nMacAddrHigh", ctypes.c_uint),
        ("nMacAddrLow", ctypes.c_uint),
        ("nTLayerType", ctypes.c_uint),
        ("nReserved", ctypes.c_uint * 4),
        ("SpecialInfo", MV_CC_DEVICE_INFO_UNION),
    ]

# 设备信息列表结构
class MV_CC_DEVICE_INFO_LIST(ctypes.Structure):
    _fields_ = [
        ("nDeviceNum", ctypes.c_uint),
        ("pDeviceInfo", ctypes.POINTER(MV_CC_DEVICE_INFO) * MV_MAX_DEVICE_NUM),
    ]


def ip_to_str(ip_int):
    """将整数IP转换为字符串"""
    return f"{(ip_int >> 24) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 8) & 0xFF}.{ip_int & 0xFF}"


def test_library_load():
    """测试 SDK 库加载"""
    print("=" * 60)
    print("海康工业相机 SDK 测试")
    print("=" * 60)
    
    # 检查库文件存在
    lib_file = f"{LIB_PATH}/libMvCameraControl.so"
    print(f"\n[1] 检查库文件: {lib_file}")
    if os.path.exists(lib_file):
        print(f"    ✓ 库文件存在")
    else:
        print(f"    ✗ 库文件不存在!")
        return None
    
    # 设置环境变量
    print(f"\n[2] 设置环境变量")
    os.environ["MVCAM_SDK_PATH"] = SDK_PATH
    os.environ["MVCAM_COMMON_RUNENV"] = f"{SDK_PATH}/lib"
    current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
    if LIB_PATH not in current_ld_path:
        os.environ["LD_LIBRARY_PATH"] = f"{LIB_PATH}:{current_ld_path}"
    print(f"    MVCAM_SDK_PATH = {SDK_PATH}")
    
    # 加载库
    print(f"\n[3] 加载 SDK 库")
    try:
        lib = ctypes.CDLL(lib_file)
        print(f"    ✓ 库加载成功!")
        return lib
    except Exception as e:
        print(f"    ✗ 加载失败: {e}")
        return None


def test_enumerate_devices(lib):
    """测试枚举相机设备"""
    print(f"\n[4] 枚举相机设备")
    
    try:
        # 获取函数
        MV_CC_EnumDevices = lib.MV_CC_EnumDevices
        MV_CC_EnumDevices.argtypes = [ctypes.c_uint, ctypes.POINTER(MV_CC_DEVICE_INFO_LIST)]
        MV_CC_EnumDevices.restype = ctypes.c_int
        
        # 枚举设备
        device_list = MV_CC_DEVICE_INFO_LIST()
        ret = MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, ctypes.byref(device_list))
        
        if ret != 0:
            print(f"    ✗ 枚举失败，错误码: 0x{ret:08X}")
            return False
        
        n_devices = device_list.nDeviceNum
        print(f"    ✓ 找到 {n_devices} 个设备")
        
        if n_devices == 0:
            print(f"\n    提示: 未检测到相机，请确保:")
            print(f"        - 相机已连接并上电")
            print(f"        - GigE 网络相机与设备在同一网段")
            print(f"        - USB 相机已正确连接")
        else:
            for i in range(n_devices):
                dev_info = device_list.pDeviceInfo[i].contents
                layer_type = dev_info.nTLayerType
                
                print(f"\n    ━━━ 设备 {i+1} ━━━")
                
                if layer_type == MV_GIGE_DEVICE:
                    print(f"    类型: GigE 网络相机")
                    gige_info = dev_info.SpecialInfo.stGigEInfo
                    print(f"    IP 地址: {ip_to_str(gige_info.nCurrentIp)}")
                    print(f"    子网掩码: {ip_to_str(gige_info.nCurrentSubNetMask)}")
                    print(f"    网关: {ip_to_str(gige_info.nDefultGateWay)}")
                    print(f"    厂商: {gige_info.chManufacturerName.decode('utf-8', errors='ignore')}")
                    print(f"    型号: {gige_info.chModelName.decode('utf-8', errors='ignore')}")
                    print(f"    序列号: {gige_info.chSerialNumber.decode('utf-8', errors='ignore')}")
                    print(f"    版本: {gige_info.chDeviceVersion.decode('utf-8', errors='ignore')}")
                    user_name = gige_info.chUserDefinedName.decode('utf-8', errors='ignore')
                    if user_name:
                        print(f"    用户名称: {user_name}")
                        
                elif layer_type == MV_USB_DEVICE:
                    print(f"    类型: USB3 相机")
                    usb_info = dev_info.SpecialInfo.stUsb3VInfo
                    print(f"    厂商: {usb_info.chManufacturerName.decode('utf-8', errors='ignore')}")
                    print(f"    型号: {usb_info.chModelName.decode('utf-8', errors='ignore')}")
                    print(f"    序列号: {usb_info.chSerialNumber.decode('utf-8', errors='ignore')}")
                    print(f"    版本: {usb_info.chDeviceVersion.decode('utf-8', errors='ignore')}")
                    print(f"    VendorID: 0x{usb_info.idVendor:04X}")
                    print(f"    ProductID: 0x{usb_info.idProduct:04X}")
                else:
                    print(f"    类型: 未知 (0x{layer_type:08X})")
        
        return True
        
    except Exception as e:
        print(f"    ✗ 枚举出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print(f"\nPython 版本: {sys.version.split()[0]}")
    print(f"运行平台: {os.uname().sysname} {os.uname().machine}")
    
    lib = test_library_load()
    if lib:
        test_enumerate_devices(lib)
    
    print("\n" + "=" * 60)
    print("SDK 安装验证完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
