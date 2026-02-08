"""
首次运行初始化脚本
- 创建桌面快捷方式指向 main.py，用 Python 运行，图标为 icon.png
- 检查 knowledge 文件夹文件数量
- 如果 <= 3，提示用户建立知识库，并自动运行 process_knowledge_base.py
"""

import os
import sys
import subprocess
import shutil
import json
import platform
import urllib.parse
import urllib.request
from pathlib import Path

# 获取脚本所在目录（项目根目录）
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT = os.path.join(PROJECT_DIR, "main.py")
ICON_ICO = os.path.join(PROJECT_DIR, "icon.ico")
ICON_PNG = os.path.join(PROJECT_DIR, "icon.png")
KNOWLEDGE_DIR = os.path.join(PROJECT_DIR, "knowledge")
PROCESS_SCRIPT = os.path.join(PROJECT_DIR, "process_knowledge_base.py")
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as exc:
        print(f"✗ 读取 config.json 失败：{exc}")
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
        print(f"✓ 配置已写入：{CONFIG_PATH}")
    except Exception as exc:
        print(f"✗ 写入 config.json 失败：{exc}")


def check_network_reachable(url="https://www.google.com/generate_204", timeout_ms=2000):
    """Check connectivity via ping + lightweight HTTPS GET. Returns True if either succeeds."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "google.com"
    is_windows = platform.system().lower().startswith("win")
    if is_windows:
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
    else:
        cmd = ["ping", "-c", "1", "-W", str(int(timeout_ms / 1000)), host]

    try:
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            return True
    except Exception as exc:
        print(f"✗ 无法执行 ping：{exc}")

    # Fallback: HTTPS request (respects proxy envs)
    try:
        with urllib.request.urlopen(url, timeout=timeout_ms / 1000.0) as resp:
            return 200 <= getattr(resp, "status", 200) < 400
    except Exception as exc:
        print(f"✗ HTTPS 连通性检测失败：{exc}")
        return False


def prompt_config_if_needed():
    cfg = load_config()

    defaults = {
        "base_url": cfg.get("base_url") or "https://api.moonshot.cn/v1",
        "model": cfg.get("model") or "kimi-latest",
    }

    if not cfg.get("system_prompt"):
        cfg["system_prompt"] = (
            "You are a WorldQuant BRAIN platform expert and Consultant. "
            "Your goal is to assist users with Alpha development, BRAIN API usage, and maximizing consultant income."
        )

    def ask(field, label, default_value=None, allow_empty=False):
        current = str(cfg.get(field, "")).strip()
        prompt = f"请输入 {label}" + (f" [默认: {current or default_value}]" if (current or default_value) else "") + ": "
        value = input(prompt).strip()
        if not value:
            value = current if current else (default_value if default_value is not None else "")
        if value or allow_empty:
            cfg[field] = value
        return value

    api_key = ask("api_key", "API Key")
    base_url = ask("base_url", "Base URL", defaults["base_url"], allow_empty=True)
    model = ask("model", "模型名称", defaults["model"], allow_empty=True)

    if api_key:
        save_config(cfg)
        return True

    print("✗ 配置文件中的 api_key 为空，请填写后再运行本脚本。")
    return False


def is_api_key_configured():
    """Check config; if api_key missing/empty, prompt user to fill and persist."""
    cfg = load_config()

    api_key = str(cfg.get("api_key", "")).strip()
    if api_key:
        return True

    print("✗ 当前 config.json 中 api_key 为空。")
    return prompt_config_if_needed()

def create_desktop_shortcut():
    """创建桌面快捷方式"""
    try:
        import win32com.client
        
        desktop = os.path.expanduser("~\\Desktop")
        shortcut_path = os.path.join(desktop, "BRAIN顾问助手.lnk")
        
        # 获取 Python 可执行文件路径
        python_exe = sys.executable
        
        # 创建 shortcut
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(shortcut_path)
        shortcut.TargetPath = python_exe
        shortcut.Arguments = f'"{MAIN_SCRIPT}"'
        shortcut.WorkingDirectory = PROJECT_DIR
        
        # 设置图标：优先使用 .ico（Windows 标准格式），再试 .png
        icon_found = False
        if os.path.exists(ICON_ICO):
            # .ico 文件：使用 "路径,0" 格式
            shortcut.IconLocation = f"{ICON_ICO},0"
            icon_found = True
            print(f"  使用图标：{ICON_ICO}")
        elif os.path.exists(ICON_PNG):
            # .png 文件：也需要 "路径,0" 格式
            shortcut.IconLocation = f"{ICON_PNG},0"
            icon_found = True
            print(f"  使用图标：{ICON_PNG}")
        else:
            # 使用 Python 可执行文件的图标作为默认
            shortcut.IconLocation = f"{python_exe},0"
            print(f"  使用默认图标（Python 图标）")
        
        shortcut.Description = "BRAIN 顾问助手 - AI 驱动的交互工具"
        shortcut.save()
        
        print(f"✓ 桌面快捷方式已创建：{shortcut_path}")
        return True
    except ImportError:
        print("⚠ pywin32 未安装，尝试使用备选方案创建快捷方式...")
        try:
            # 备选方案：使用 Windows API
            create_shortcut_via_batch(desktop, shortcut_path, python_exe)
            return True
        except Exception as e:
            print(f"✗ 创建快捷方式失败：{e}")
            print(f"  请手动创建快捷方式，目标为：{python_exe} \"{MAIN_SCRIPT}\"")
            return False
    except Exception as e:
        print(f"✗ 创建快捷方式失败：{e}")
        return False

def check_knowledge_base():
    """检查 knowledge 文件夹中的文件数量"""
    if not os.path.exists(KNOWLEDGE_DIR):
        os.makedirs(KNOWLEDGE_DIR)
        print(f"✓ 创建 knowledge 文件夹：{KNOWLEDGE_DIR}")
        return 0
    
    # 只计算文件，不计算目录
    files = [f for f in os.listdir(KNOWLEDGE_DIR) if os.path.isfile(os.path.join(KNOWLEDGE_DIR, f))]
    file_count = len(files)
    print(f"知识库文件数量：{file_count}")
    
    if files:
        print(f"  已有文件：{', '.join(files)}")
    
    return file_count

def run_process_knowledge_base():
    """运行 process_knowledge_base.py 建立知识库"""
    if not os.path.exists(PROCESS_SCRIPT):
        print(f"✗ 找不到 {PROCESS_SCRIPT}")
        return False
    
    print(f"\n正在运行知识库初始化脚本...")
    print(f"命令：{sys.executable} \"{PROCESS_SCRIPT}\"")
    
    try:
        subprocess.run([sys.executable, PROCESS_SCRIPT], cwd=PROJECT_DIR)
        print("✓ 知识库初始化完成")
        return True
    except Exception as e:
        print(f"✗ 运行 process_knowledge_base.py 失败：{e}")
        return False

def main():
    print("=" * 60)
    print("BRAIN 顾问助手 - 首次运行初始化")
    print("=" * 60)
    print()

    # 0. 检查 api_key 是否已配置，未配置则直接退出
    if not is_api_key_configured():
        input("按 Enter 键退出...")
        return

    # 0.1 检查网络（ping + HTTPS），以确认代理已开启
    print("[网络检查] 正在测试到 https://www.google.com 的连通性...")
    if not check_network_reachable("https://www.google.com/generate_204"):
        print("✗ 无法连通 google.com，请确认代理已开启，然后重新运行本脚本。")
        input("按 Enter 键退出...")
        return
    print("✓ 网络检查通过")
    
    # 1. 创建桌面快捷方式
    print("[1/2] 创建桌面快捷方式...")
    shortcut_ok = create_desktop_shortcut()
    print()
    
    # 2. 检查知识库
    print("[2/2] 检查本地知识库...")
    file_count = check_knowledge_base()
    print()
    
    if file_count <= 3:
        print("⚠ 知识库文件较少（<= 3 个）")
        print("建议建立本地知识库以增强 AI 回答效果")
        print()
        
        response = input("是否现在运行知识库初始化脚本？(y/n) [默认: y]: ").strip().lower()
        if response != 'n':
            run_process_knowledge_base()
    else:
        print(f"✓ 知识库已初始化（包含 {file_count} 个文件）")
    
    print()
    print("=" * 60)
    print("初始化完成！")
    print("=" * 60)
    print()
    
    if shortcut_ok:
        print("📌 你现在可以从桌面快捷方式启动应用")
        print(f"   或者运行：{sys.executable} \"{MAIN_SCRIPT}\"")
    else:
        print(f"请运行：{sys.executable} \"{MAIN_SCRIPT}\"")
    print()
    
    input("按 Enter 键退出...")

if __name__ == "__main__":
    main()
