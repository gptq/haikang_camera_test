#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海康工业相机 SDK 环境检查工具
检查所有必需组件是否正确安装和配置
"""

import os
import sys
import ctypes
import subprocess
from pathlib import Path

# 检查项结果
results = []

def check_pass(item, detail=""):
    """检查通过"""
    results.append(("✓", item, detail))
    print(f"[✓] {item}" + (f": {detail}" if detail else ""))

def check_fail(item, detail=""):
    """检查失败"""
    results.append(("✗", item, detail))
    print(f"[✗] {item}" + (f": {detail}" if detail else ""))

def check_warn(item, detail=""):
    """检查警告"""
    results.append(("!", item, detail))
    print(f"[!] {item}" + (f": {detail}" if detail else ""))


def check_sdk_path():
    """检查 SDK 安装路径"""
    sdk_path = os.environ.get("MVCAM_SDK_PATH", "/opt/MVS")
    if os.path.isdir(sdk_path):
        check_pass("SDK 路径", sdk_path)
        return sdk_path
    else:
        check_fail("SDK 路径", f"{sdk_path} 不存在")
        return None


def check_library(sdk_path):
    """检查 SDK 库文件"""
    if not sdk_path:
        check_fail("SDK 库文件", "SDK 路径不存在")
        return False
    
    lib_path = os.path.join(sdk_path, "lib", "aarch64", "libMvCameraControl.so")
    if os.path.isfile(lib_path):
        check_pass("SDK 库文件", "libMvCameraControl.so")
        return True
    else:
        check_fail("SDK 库文件", f"{lib_path} 不存在")
        return False


def check_python_binding(sdk_path):
    """检查 Python 绑定"""
    if not sdk_path:
        check_fail("Python 绑定", "SDK 路径不存在")
        return False
    
    # 检查两个可能的路径
    paths = [
        os.path.join(sdk_path, "Samples", "64", "Python", "MvImport", "MvCameraControl_class.py"),
        os.path.join(sdk_path, "Samples", "aarch64", "Python", "MvImport", "MvCameraControl_class.py"),
    ]
    
    for path in paths:
        if os.path.isfile(path) or os.path.islink(path):
            check_pass("Python 绑定", "MvCameraControl_class.py")
            return True
    
    check_fail("Python 绑定", "MvCameraControl_class.py 未找到")
    return False


def check_env_vars():
    """检查环境变量"""
    required_vars = ["MVCAM_SDK_PATH", "MVCAM_COMMON_RUNENV"]
    missing = []
    
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)
    
    if not missing:
        check_pass("环境变量", ", ".join(required_vars))
        return True
    else:
        check_fail("环境变量", f"缺少: {', '.join(missing)}")
        return False


def check_ld_library_path():
    """检查 LD_LIBRARY_PATH"""
    ld_path = os.environ.get("LD_LIBRARY_PATH", "")
    if "/opt/MVS/lib/aarch64" in ld_path:
        check_pass("LD_LIBRARY_PATH", "包含 /opt/MVS/lib/aarch64")
        return True
    else:
        check_warn("LD_LIBRARY_PATH", "未包含 /opt/MVS/lib/aarch64")
        return False


def check_network_capability():
    """检查 Python 网络权限"""
    try:
        result = subprocess.run(
            ["getcap", sys.executable],
            capture_output=True,
            text=True
        )
        if "cap_net_raw" in result.stdout:
            check_pass("网络权限", "cap_net_raw 已设置")
            return True
        else:
            # 检查真实路径
            real_python = os.path.realpath(sys.executable)
            result = subprocess.run(
                ["getcap", real_python],
                capture_output=True,
                text=True
            )
            if "cap_net_raw" in result.stdout:
                check_pass("网络权限", f"cap_net_raw ({real_python})")
                return True
            else:
                check_warn("网络权限", "未设置 cap_net_raw，GigE 相机可能需要 sudo")
                return False
    except Exception as e:
        check_warn("网络权限", f"无法检查: {e}")
        return False


def check_library_load():
    """检查库能否加载"""
    lib_path = "/opt/MVS/lib/aarch64/libMvCameraControl.so"
    try:
        lib = ctypes.CDLL(lib_path)
        check_pass("库加载测试", "libMvCameraControl.so 可加载")
        return lib
    except Exception as e:
        check_fail("库加载测试", str(e))
        return None


def check_camera_enum(lib):
    """检查相机枚举"""
    if not lib:
        check_fail("相机枚举", "库未加载")
        return
    
    try:
        # 添加 MvImport 到路径
        sys.path.insert(0, "/opt/MVS/Samples/64/Python/MvImport")
        from MvCameraControl_class import MvCamera
        from CameraParams_header import MV_CC_DEVICE_INFO_LIST, MV_GIGE_DEVICE, MV_USB_DEVICE
        
        device_list = MV_CC_DEVICE_INFO_LIST()
        ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, device_list)
        
        if ret == 0:
            n = device_list.nDeviceNum
            if n > 0:
                check_pass("相机枚举", f"找到 {n} 个设备")
            else:
                check_warn("相机枚举", "未检测到相机，请确认相机已连接")
        else:
            check_fail("相机枚举", f"错误码: 0x{ret:08X}")
    except Exception as e:
        check_fail("相机枚举", str(e))


def check_hik_camera_module():
    """检查 hik_camera 第三方模块"""
    try:
        from hik_camera import HikCamera
        check_pass("hik_camera 模块", "可导入")
        return True
    except ImportError:
        check_warn("hik_camera 模块", "未安装 (可选)")
        return False
    except Exception as e:
        check_warn("hik_camera 模块", str(e))
        return False


def print_summary():
    """打印检查摘要"""
    print("\n" + "=" * 50)
    passed = sum(1 for r in results if r[0] == "✓")
    failed = sum(1 for r in results if r[0] == "✗")
    warned = sum(1 for r in results if r[0] == "!")
    
    print(f"检查完成: {passed} 通过, {failed} 失败, {warned} 警告")
    
    if failed == 0:
        print("\n✅ SDK 环境配置正确，可以正常使用！")
    else:
        print("\n❌ 存在问题，请参考 INSTALL_GUIDE.md 修复")


def main():
    """主函数"""
    print("=" * 50)
    print("海康工业相机 SDK 环境检查")
    print("=" * 50)
    print(f"\nPython: {sys.version.split()[0]}")
    print(f"平台: {os.uname().sysname} {os.uname().machine}")
    print()
    
    sdk_path = check_sdk_path()
    check_library(sdk_path)
    check_python_binding(sdk_path)
    check_env_vars()
    check_ld_library_path()
    check_network_capability()
    lib = check_library_load()
    check_camera_enum(lib)
    check_hik_camera_module()
    
    print_summary()


if __name__ == "__main__":
    main()
