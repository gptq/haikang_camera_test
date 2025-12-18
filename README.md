# 海康工业相机 (Hikrobot) SDK for RK3588

[![Platform](https://img.shields.io/badge/Platform-RK3588-blue.svg)](https://www.rock-chips.com/)
[![Architecture](https://img.shields.io/badge/Arch-aarch64-green.svg)]()
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

在 RK3588 + aarch64 Linux 系统上部署海康工业相机 SDK 的工具集，包含一键安装脚本、环境检查工具和使用示例。

## 📦 文件结构

```
haikang_camera_test/
├── README.md                    # 本文件
├── INSTALL_GUIDE.md             # 详细安装经验文档
├── install_hikrobot_sdk.sh      # 一键安装脚本
├── check_environment.py         # 环境检查工具
├── test_sdk.py                  # SDK 基础测试
└── test_full_camera.py          # 完整相机功能测试
```

---

## 🚀 快速开始

### 前置条件

- RK3588 开发板 (或其他 aarch64 Linux 设备)
- Ubuntu 20.04/22.04
- 海康工业相机 (GigE/USB3)
- **MVS SDK 完整开发包** (非 Runtime 包)

### 一键安装

```bash
# 1. 下载 MVS SDK 完整包（从海康官网）
#    例如: MVS-3.0.1_aarch64_20251113.deb

# 2. 克隆本仓库
git clone <repo-url> haikang_camera_test
cd haikang_camera_test

# 3. 执行一键安装
chmod +x install_hikrobot_sdk.sh
sudo ./install_hikrobot_sdk.sh /path/to/MVS-3.0.1_aarch64_20251113.deb

# 4. 加载环境变量
source ~/.bashrc

# 5. 验证安装
python3 test_sdk.py
```

---

## 🔍 环境检查

运行环境检查脚本，确认所有组件正确安装：

```bash
python3 check_environment.py
```

**预期输出**:
```
[✓] SDK 路径: /opt/MVS
[✓] 库文件: libMvCameraControl.so
[✓] Python 绑定: MvCameraControl_class.py
[✓] 环境变量: MVCAM_SDK_PATH, MVCAM_COMMON_RUNENV
[✓] 网络权限: cap_net_raw
[✓] 相机枚举: 找到 1 个设备
```

---

## 📖 安装详解

### 方式一：使用一键脚本（推荐）

```bash
sudo ./install_hikrobot_sdk.sh MVS-3.0.1_aarch64_20251113.deb
```

脚本自动完成：
- SDK 安装
- 符号链接创建 (`64 → aarch64`)
- 环境变量配置
- Python 虚拟环境配置
- GigE 网络权限设置
- udev 规则配置

### 方式二：手动安装

参见 [INSTALL_GUIDE.md](INSTALL_GUIDE.md)

---

## 🎥 使用示例

### 基础测试

```bash
# 测试 SDK 加载和相机枚举
python3 test_sdk.py
```

### 完整相机测试

```bash
# 测试连接、取图、释放资源
python3 test_full_camera.py
```

### Python 代码示例

```python
import os
import sys

# 设置环境
os.environ.setdefault("MVCAM_SDK_PATH", "/opt/MVS")
os.environ.setdefault("MVCAM_COMMON_RUNENV", "/opt/MVS/lib")
sys.path.insert(0, "/opt/MVS/Samples/64/Python/MvImport")

from MvCameraControl_class import MvCamera
from CameraParams_header import *

# 枚举设备
device_list = MV_CC_DEVICE_INFO_LIST()
MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, device_list)
print(f"找到 {device_list.nDeviceNum} 个相机")
```

### 使用 hik_camera 第三方库

```python
from hik_camera import HikCamera

# 连接相机 (需要指定 IP)
cam = HikCamera("192.168.2.124")

# 取图
frame = cam.get_frame()

# 释放
del cam
```

---

## ⚠️ 常见问题

### Q: 安装时内核模块编译失败？

```
*** Fail to create the module gevframegrabber.ko ***
```

**A**: 对于 GigE 网络相机，可以**忽略此错误**。这些驱动仅用于 PCIe 采集卡。

### Q: 找不到 MvCameraControl_class.py？

**A**: 确保使用 **完整 SDK 包**（非 Runtime 包），或手动创建符号链接：
```bash
sudo mkdir -p /opt/MVS/Samples/64/Python
sudo ln -sf /opt/MVS/Samples/aarch64/Python/MvImport /opt/MVS/Samples/64/Python/MvImport
```

### Q: 打开设备失败 0x80000203？

**A**: 权限不足，设置 Python 网络能力：
```bash
sudo setcap cap_net_raw,cap_net_admin=eip /usr/bin/python3.10
```

### Q: XOpenDisplay Fail 警告？

**A**: 无图形界面环境的正常警告，**不影响功能**。

---

## 📋 环境要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Ubuntu 20.04/22.04 (aarch64) |
| Python | 3.8+ |
| SDK 版本 | MVS 3.0+ |
| 相机接口 | GigE / USB3 |

---

## 📚 参考文档

- [INSTALL_GUIDE.md](INSTALL_GUIDE.md) - 详细安装经验和故障排除
- [海康机器人官网](https://www.hikrobotics.com/) - 下载 SDK
- `/opt/MVS/doc/` - SDK 官方文档

---

## 📄 License

本工具集仅供内部使用。海康 MVS SDK 受海康机器人版权保护。
