#!/bin/bash
#
# 海康工业相机 (Hikrobot) MVS SDK 一键安装脚本
# 适用于 RK3588 + aarch64 Linux 系统
#
# 使用方法：
#   chmod +x install_hikrobot_sdk.sh
#   sudo ./install_hikrobot_sdk.sh [MVS_DEB_FILE]
#
# 示例：
#   sudo ./install_hikrobot_sdk.sh MVS-3.0.1_aarch64_20251113.deb
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# 检查 root 权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "请使用 sudo 运行此脚本"
        exit 1
    fi
}

# 检查系统架构
check_arch() {
    ARCH=$(uname -m)
    if [ "$ARCH" != "aarch64" ]; then
        log_error "此脚本仅支持 aarch64 架构，当前架构: $ARCH"
        exit 1
    fi
    log_info "系统架构: $ARCH ✓"
}

# 检查是否为 RK3588
check_rk3588() {
    if grep -q "rk3588" /proc/device-tree/compatible 2>/dev/null; then
        log_info "检测到 RK3588 平台 ✓"
    else
        log_warn "未检测到 RK3588 平台，脚本可能需要调整"
    fi
}

# 查找 MVS 安装包
find_mvs_package() {
    if [ -n "$1" ] && [ -f "$1" ]; then
        MVS_PACKAGE="$1"
    else
        # 自动查找当前目录下的 MVS 包
        MVS_PACKAGE=$(ls MVS-*.deb 2>/dev/null | head -1)
        if [ -z "$MVS_PACKAGE" ]; then
            MVS_PACKAGE=$(ls *MVS*.deb 2>/dev/null | grep -v Runtime | head -1)
        fi
    fi
    
    if [ -z "$MVS_PACKAGE" ] || [ ! -f "$MVS_PACKAGE" ]; then
        log_error "未找到 MVS SDK 安装包"
        log_info "请下载完整 SDK 包（非 Runtime 包），例如:"
        log_info "  MVS-3.0.1_aarch64_20251113.deb"
        log_info ""
        log_info "用法: sudo $0 <MVS安装包.deb>"
        exit 1
    fi
    
    # 检查是否为 Runtime 包
    if echo "$MVS_PACKAGE" | grep -qi "runtime"; then
        log_error "检测到 Runtime 包: $MVS_PACKAGE"
        log_error "Runtime 包不包含 Python 绑定，请使用完整 SDK 包"
        exit 1
    fi
    
    log_info "找到安装包: $MVS_PACKAGE ✓"
}

# 安装 SDK
install_mvs_sdk() {
    log_step "安装 MVS SDK..."
    
    # 卸载旧版本（如果存在）
    if dpkg -l | grep -q "mvs\|mvcamctrlsdk"; then
        log_info "卸载旧版本..."
        dpkg --purge mvs mvcamctrlsdk 2>/dev/null || true
    fi
    
    # 安装新版本
    dpkg -i "$MVS_PACKAGE"
    
    if [ -d "/opt/MVS" ]; then
        log_info "SDK 安装完成 ✓"
    else
        log_error "SDK 安装失败，/opt/MVS 目录不存在"
        exit 1
    fi
}

# 创建兼容性符号链接
create_symlinks() {
    log_step "创建兼容性符号链接..."
    
    # Python 路径兼容
    if [ -d "/opt/MVS/Samples/aarch64/Python/MvImport" ]; then
        mkdir -p /opt/MVS/Samples/64/Python
        ln -sf /opt/MVS/Samples/aarch64/Python/MvImport /opt/MVS/Samples/64/Python/MvImport
        log_info "创建 Python MvImport 符号链接 ✓"
    fi
    
    # OpenCV 路径兼容（如果存在）
    if [ -d "/opt/MVS/Samples/aarch64/OpenCV" ]; then
        mkdir -p /opt/MVS/Samples/64
        ln -sf /opt/MVS/Samples/aarch64/OpenCV /opt/MVS/Samples/64/OpenCV 2>/dev/null || true
    fi
}

# 配置环境变量
setup_environment() {
    log_step "配置环境变量..."
    
    ENV_CONFIG="
# Hikrobot MVS SDK 环境变量
export MVCAM_SDK_PATH=/opt/MVS
export MVCAM_COMMON_RUNENV=/opt/MVS/lib
export MVCAM_SDK_VERSION=4.7.0
export MVCAM_GENICAM_CLPROTOCOL=/opt/MVS/lib/CLProtocol
export ALLUSERSPROFILE=/opt/MVS/MVFG
export LD_LIBRARY_PATH=/opt/MVS/lib/aarch64:\$LD_LIBRARY_PATH
"
    
    # 添加到 /etc/profile.d/
    echo "$ENV_CONFIG" > /etc/profile.d/hikrobot_mvs.sh
    chmod +x /etc/profile.d/hikrobot_mvs.sh
    log_info "环境变量配置到 /etc/profile.d/hikrobot_mvs.sh ✓"
    
    # 同时添加到调用用户的 bashrc
    REAL_USER=${SUDO_USER:-$USER}
    REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
    
    if [ -f "$REAL_HOME/.bashrc" ]; then
        if ! grep -q "MVCAM_SDK_PATH" "$REAL_HOME/.bashrc"; then
            echo "$ENV_CONFIG" >> "$REAL_HOME/.bashrc"
            log_info "环境变量配置到 $REAL_HOME/.bashrc ✓"
        else
            log_info "$REAL_HOME/.bashrc 已包含 MVS 环境变量"
        fi
    fi
}

# 配置 Python 虚拟环境（如果存在）
setup_venv() {
    log_step "检查 Python 虚拟环境..."
    
    REAL_USER=${SUDO_USER:-$USER}
    REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
    
    # 常见虚拟环境路径
    VENV_PATHS=(
        "$REAL_HOME/hailo_venv"
        "$REAL_HOME/venv"
        "$REAL_HOME/.venv"
    )
    
    ENV_LINES="
# Hikrobot MVS SDK
export MVCAM_SDK_PATH=/opt/MVS
export MVCAM_COMMON_RUNENV=/opt/MVS/lib
export LD_LIBRARY_PATH=/opt/MVS/lib/aarch64:\$LD_LIBRARY_PATH"
    
    for VENV_PATH in "${VENV_PATHS[@]}"; do
        if [ -f "$VENV_PATH/bin/activate" ]; then
            if ! grep -q "MVCAM_SDK_PATH" "$VENV_PATH/bin/activate"; then
                echo "$ENV_LINES" >> "$VENV_PATH/bin/activate"
                log_info "环境变量配置到 $VENV_PATH/bin/activate ✓"
            else
                log_info "$VENV_PATH 已包含 MVS 环境变量"
            fi
        fi
    done
}

# 配置 GigE 相机网络权限
setup_gige_permissions() {
    log_step "配置 GigE 相机网络权限..."
    
    # 查找系统 Python 解释器
    PYTHON_PATHS=(
        "/usr/bin/python3.10"
        "/usr/bin/python3.11"
        "/usr/bin/python3.12"
        "/usr/bin/python3"
    )
    
    for PYTHON_PATH in "${PYTHON_PATHS[@]}"; do
        if [ -f "$PYTHON_PATH" ] && [ ! -L "$PYTHON_PATH" ]; then
            setcap cap_net_raw,cap_net_admin=eip "$PYTHON_PATH" 2>/dev/null && \
                log_info "已为 $PYTHON_PATH 配置网络权限 ✓" || \
                log_warn "无法为 $PYTHON_PATH 配置权限"
        elif [ -L "$PYTHON_PATH" ]; then
            REAL_PYTHON=$(readlink -f "$PYTHON_PATH")
            if [ -f "$REAL_PYTHON" ]; then
                setcap cap_net_raw,cap_net_admin=eip "$REAL_PYTHON" 2>/dev/null && \
                    log_info "已为 $REAL_PYTHON 配置网络权限 ✓" || \
                    log_warn "无法为 $REAL_PYTHON 配置权限"
            fi
        fi
    done
}

# 配置 udev 规则
setup_udev_rules() {
    log_step "配置 udev 规则..."
    
    # USB 相机规则
    if [ ! -f "/etc/udev/rules.d/80-hikrobot-usb.rules" ]; then
        cat > /etc/udev/rules.d/80-hikrobot-usb.rules << 'EOF'
# Hikrobot USB cameras
SUBSYSTEM=="usb", ATTRS{idVendor}=="2bdf", MODE="0666"
EOF
        log_info "USB 相机 udev 规则已创建 ✓"
    fi
    
    # 重新加载 udev 规则
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger 2>/dev/null || true
}

# 验证安装
verify_installation() {
    log_step "验证安装..."
    
    # 检查关键文件
    REQUIRED_FILES=(
        "/opt/MVS/lib/aarch64/libMvCameraControl.so"
        "/opt/MVS/Samples/64/Python/MvImport/MvCameraControl_class.py"
    )
    
    ALL_OK=true
    for FILE in "${REQUIRED_FILES[@]}"; do
        if [ -f "$FILE" ] || [ -L "$FILE" ]; then
            log_info "检查 $FILE ✓"
        else
            log_error "缺少文件: $FILE"
            ALL_OK=false
        fi
    done
    
    if [ "$ALL_OK" = true ]; then
        log_info "所有关键文件检查通过 ✓"
    else
        log_error "安装验证失败"
        exit 1
    fi
}

# 创建测试脚本
create_test_script() {
    log_step "创建测试脚本..."
    
    TEST_SCRIPT="/opt/MVS/test_camera.py"
    
    cat > "$TEST_SCRIPT" << 'PYTHONEOF'
#!/usr/bin/env python3
"""海康工业相机快速测试脚本"""

import os
import sys

os.environ.setdefault("MVCAM_SDK_PATH", "/opt/MVS")
os.environ.setdefault("MVCAM_COMMON_RUNENV", "/opt/MVS/lib")

sys.path.insert(0, "/opt/MVS/Samples/64/Python/MvImport")

from MvCameraControl_class import MvCamera
from CameraParams_header import MV_CC_DEVICE_INFO_LIST, MV_GIGE_DEVICE, MV_USB_DEVICE

def main():
    print("=" * 50)
    print("海康工业相机 SDK 快速测试")
    print("=" * 50)
    
    device_list = MV_CC_DEVICE_INFO_LIST()
    ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, device_list)
    
    if ret != 0:
        print(f"枚举失败: 0x{ret:08X}")
        return
    
    print(f"\n找到 {device_list.nDeviceNum} 个相机设备")
    
    if device_list.nDeviceNum == 0:
        print("\n提示: 请确保相机已连接并在同一网段")
    else:
        print("\n✓ SDK 安装成功，相机可用!")

if __name__ == "__main__":
    main()
PYTHONEOF

    chmod +x "$TEST_SCRIPT"
    log_info "测试脚本创建于 $TEST_SCRIPT ✓"
}

# 打印安装完成信息
print_summary() {
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}              海康工业相机 SDK 安装完成！                    ${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "安装路径: /opt/MVS"
    echo ""
    echo "验证安装:"
    echo "  source ~/.bashrc"
    echo "  python3 /opt/MVS/test_camera.py"
    echo ""
    echo "Python 使用示例:"
    echo "  from hik_camera import HikCamera"
    echo "  cam = HikCamera('192.168.x.x')"
    echo ""
    echo -e "${YELLOW}注意: 请在新终端中运行，或执行 'source ~/.bashrc' 加载环境变量${NC}"
    echo ""
}

# 主函数
main() {
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "         海康工业相机 (Hikrobot) MVS SDK 一键安装           "
    echo "              适用于 RK3588 + aarch64 Linux                "
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    
    check_root
    check_arch
    check_rk3588
    find_mvs_package "$1"
    
    echo ""
    log_info "开始安装..."
    echo ""
    
    install_mvs_sdk
    create_symlinks
    setup_environment
    setup_venv
    setup_gige_permissions
    setup_udev_rules
    verify_installation
    create_test_script
    
    print_summary
}

# 执行主函数
main "$@"
