import subprocess
import webview
import time
import sys
import os
import requests
import threading
import warnings

# 忽略依赖警告
warnings.filterwarnings("ignore", category=UserWarning)

def get_base_path():
    if getattr(sys, 'frozen', False): 
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def start_backend():
    base_path = get_base_path()
    try:
        # 尝试清理旧进程
        if sys.platform == 'darwin':
            subprocess.run(["lsof -ti:8100 | xargs kill -9"], shell=True, stderr=subprocess.DEVNULL)
    except: pass

    # 打包模式下直接启动自身作为后端
    executable = sys.executable
    if getattr(sys, 'frozen', False):
        args = [executable, "--backend-only"]
    else:
        script_path = os.path.abspath(sys.argv[0])
        args = [executable, script_path, "--backend-only"]
    
    env = os.environ.copy()
    # 关键：确保 PYTHONPATH 包含解压后的资源目录
    editor_dir = os.path.join(base_path, 'vlog-subtitle-agent', 'scripts', 'subtitle_editor')
    env["PYTHONPATH"] = editor_dir + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
    
    # 增加调试日志到家目录方便查看
    log_path = os.path.expanduser("~/VlogStudio_backend.log")
    log_file = open(log_path, "w")
    subprocess.Popen(args, env=env, stdout=log_file, stderr=log_file)

def run_actual_backend():
    try:
        base_path = get_base_path()
        scripts_dir = os.path.join(base_path, 'vlog-subtitle-agent', 'scripts', 'subtitle_editor')
        sys.path.insert(0, scripts_dir)
        import uvicorn
        from backend_main import app
        uvicorn.run(app, host="127.0.0.1", port=8100, log_level="info")
    except Exception as e:
        with open("/tmp/vlog_err.txt", "w") as f: f.write(str(e))

# 定义原生 API 类
class Api:
    def __init__(self):
        self.window = None

    def set_window(self, window):
        self.window = window

    def select_file(self):
        if not self.window: return None
        result = self.window.create_file_dialog(
            webview.FileDialog.OPEN, 
            file_types=('Video files (*.mp4;*.mkv;*.mov)', 'All files (*.*)')
        )
        return result[0] if result else None

    def select_folder(self):
        if not self.window: return None
        result = self.window.create_file_dialog(
            webview.FileDialog.FOLDER
        )
        return result[0] if result else None

if __name__ == '__main__':
    if "--backend-only" in sys.argv:
        run_actual_backend()
        sys.exit(0)

    start_backend()

    loading_html = """
    <body style="background:#000; color:#3b82f6; display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; font-family:sans-serif; margin:0;">
        <div style="text-align:center;">
            <h2 style="font-weight:200; letter-spacing:5px;">VLOG STUDIO</h2>
            <div id="loader" style="width:20px; height:20px; border:2px solid #222; border-top-color:#3b82f6; border-radius:50%; animation:spin 1s linear infinite; margin:20px auto;"></div>
            <p id="msg" style="color:#444; font-size:10px;">INITIALIZING ENGINE...</p>
        </div>
        <style>@keyframes spin { to { transform: rotate(360deg); } }</style>
        <script>
            function check() {
                fetch('http://127.0.0.1:8100/api/status').then(r => { if(r.ok) window.location.href='http://127.0.0.1:8100/'; else setTimeout(check, 1000); }).catch(() => setTimeout(check, 1000));
            }
            check();
        </script>
    </body>
    """

    # 1. 先实例化 API
    api = Api()

    # 2. 在创建窗口时通过 js_api 传入
    window = webview.create_window(
        'Vlog AI Studio Pro', 
        html=loading_html,
        width=1400, height=900,
        background_color='#000000',
        js_api=api
    )

    # 3. 将 window 引用回填给 api 实例
    api.set_window(window)

    # 尝试在窗口加载后动态设置 macOS Dock 图标
    def set_mac_icon():
        try:
            import objc
            from AppKit import NSApplication, NSImage
            app_inst = NSApplication.sharedApplication()
            logo_path = os.path.join(get_base_path(), 'data', 'logo.png')
            if os.path.exists(logo_path):
                img = NSImage.alloc().initWithContentsOfFile_(logo_path)
                if img:
                    app_inst.setApplicationIconImage_(img)
        except Exception:
            pass
            
    window.events.shown += set_mac_icon

    # 强制禁用调试模式，防止显示 Web Inspector
    webview.start(debug=False)
