# 海康工业相机 SDK (MVS) 在 RK3588 上的安装指南

> 作者：自动化测试团队  
> 日期：2024-12-18  
> 适用平台：RK3588 + aarch64 Linux

## 📋 背景

在工业视觉应用中，需要在 RK3588 边缘计算设备上集成海康工业相机（Hikrobot）。本文档记录了完整的安装过程、遇到的问题及解决方案。

### 设备环境

| 项目 | 信息 |
|------|------|
| 开发板 | RK3588 |
| 操作系统 | Ubuntu 22.04 (aarch64) |
| 内核版本 | 5.10.209 |
| 相机型号 | Hikrobot MV-CU060-10GC |
| 相机接口 | GigE (千兆网络) |

---

## ❌ 失败经验

### 问题 1：Runtime 包安装时内核模块编译失败

**现象**：
```bash
sudo dpkg -i MvCamCtrlSDK_Runtime-4.7.0_aarch64_20251113.deb
# 输出：
# *** Fail to create the module gevframegrabber.ko ***
# *** Fail to create the module cmlframegrabber.ko ***
# *** Fail to create the module mvfgvirtualserial.ko ***
```

**根因分析**：
1. RK3588 运行的是定制内核 **5.10.209**
2. 系统安装的 linux-headers 是 **5.15.0-164**（Ubuntu 通用版本）
3. 版本不匹配导致内核模块无法编译
4. **Runtime 包的 aarch64 目录下没有预编译的 .ko 文件**（目录为空）

**结论**：内核模块失败**不影响 GigE 网络相机使用**，因为网络相机使用用户态 SDK 库，不需要内核驱动。

---

### 问题 2：Runtime 包缺少 Python 绑定

**现象**：
```python
import MvCameraControl_class as hik
# ModuleNotFoundError: No module named 'MvCameraControl_class'
```

**根因**：
- `MvCamCtrlSDK_Runtime` 是精简的运行时包
- 不包含 `/opt/MVS/Samples/` 目录
- 缺少 `MvCameraControl_class.py` 等 Python 封装文件

**解决方案**：必须安装完整的 **MVS SDK 开发包**（非 Runtime 包）。

---

### 问题 3：Python 绑定路径不匹配

**现象**：
```
ERROR: can't find MvCameraControl_class.py in: /opt/MVS/Samples/64/Python/MvImport
```

**根因**：
- 某些第三方库（如 `hik_camera`）硬编码路径为 `.../64/Python/MvImport`
- 但 aarch64 版 SDK 实际路径是 `.../aarch64/Python/MvImport`

**解决方案**：创建符号链接
```bash
sudo mkdir -p /opt/MVS/Samples/64/Python
sudo ln -sf /opt/MVS/Samples/aarch64/Python/MvImport /opt/MVS/Samples/64/Python/MvImport
```

---

### 问题 4：环境变量缺失

**现象**：
```python
TypeError: unsupported operand type(s) for +: 'NoneType' and 'str'
# 在 MvCameraControl_class.py 第 52 行
```

**根因**：`MVCAM_COMMON_RUNENV` 环境变量未设置

**解决方案**：设置完整的环境变量
```bash
export MVCAM_SDK_PATH=/opt/MVS
export MVCAM_COMMON_RUNENV=/opt/MVS/lib
export LD_LIBRARY_PATH=/opt/MVS/lib/aarch64:$LD_LIBRARY_PATH
```

---

### 问题 5：GigE 相机访问权限不足

**现象**：
```
打开设备失败: 0x80000203
# MV_E_ACCESS_DENIED - 设备无访问权限
```

**根因**：GigE 相机需要原始套接字权限（CAP_NET_RAW）

**解决方案**：为 Python 解释器添加网络能力
```bash
sudo setcap cap_net_raw,cap_net_admin=eip /usr/bin/python3.10
```

---

## ✅ 成功经验

### 正确的安装流程

1. **下载完整 SDK 开发包**（非 Runtime 包）
   - 文件示例：`MVS-3.0.1_aarch64_20251113.deb`

2. **安装 SDK**
   ```bash
   sudo dpkg -i MVS-3.0.1_aarch64_20251113.deb
   ```

3. **创建兼容性符号链接**
   ```bash
   sudo mkdir -p /opt/MVS/Samples/64/Python
   sudo ln -sf /opt/MVS/Samples/aarch64/Python/MvImport /opt/MVS/Samples/64/Python/MvImport
   ```

4. **配置环境变量**（添加到 `~/.bashrc` 或虚拟环境的 `activate`）
   ```bash
   export MVCAM_SDK_PATH=/opt/MVS
   export MVCAM_COMMON_RUNENV=/opt/MVS/lib
   export LD_LIBRARY_PATH=/opt/MVS/lib/aarch64:$LD_LIBRARY_PATH
   ```

5. **配置 GigE 相机访问权限**
   ```bash
   sudo setcap cap_net_raw,cap_net_admin=eip /usr/bin/python3.10
   ```

6. **验证安装**
   ```bash
   python3 /userdata/haikang_camera_test/test_full_camera.py
   ```

---

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `MVS-x.x.x_aarch64_xxxxxx.deb` | 完整 SDK 开发包（**必须**） |
| `MvCamCtrlSDK_Runtime-x.x.x_aarch64_xxxxxx.deb` | 精简运行时包（缺少 Python 绑定） |

---

## 🔧 常见问题

### Q: 内核模块编译失败怎么办？
**A**: 对于 GigE 网络相机，可以忽略。这些驱动只用于 PCIe 采集卡。

### Q: `XOpenDisplay Fail` 警告是什么？
**A**: 无图形界面（headless）环境的正常警告，不影响功能。

### Q: 如何切换相机 IP？
**A**: 使用海康官方 MVS 客户端配置，或在代码中直接指定目标 IP。

---

## 📌 关键点总结

1. **使用完整 SDK 包**，不要使用 Runtime 包
2. **内核模块失败可忽略**（GigE 相机不需要）
3. **创建 64 → aarch64 符号链接**确保第三方库兼容
4. **配置所有必需环境变量**
5. **setcap 设置网络权限**使普通用户可访问 GigE 相机
