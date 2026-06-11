"""
影视匠 OBS 管理工具箱 v3.5
===========================
Professional OBS Process & Configuration Manager
- Real-time process scanning with search
- Categorized process killing (OBS / ASUS / Streaming / Others)
- OBS config backup & reset
- One-click complete cleanup
- ASUS-specific process killer
- One-click OBS fix-all (diagnose + repair)
- Plugin manager (scan, selective delete, bulk delete)
- Beautiful dark-themed UI with gold accents
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import ctypes
import sys
import os
import threading
import time
from datetime import datetime
from pathlib import Path
import traceback

# ─── ttkbootstrap removed: manual dark theme used instead ───
# (ttkbootstrap .tcl theme files don't resolve in PyInstaller frozen EXEs)
HAS_TTKB = False

# ─── Try Pillow for icon ───
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ═══════════════════════════════════════════════════════════
# COLOR SCHEME - Dark theme with gold accents
# ═══════════════════════════════════════════════════════════
COLORS = {
    'bg_dark':       '#1a1a2e',
    'bg_panel':      '#16213e',
    'bg_card':       '#0f3460',
    'bg_input':      '#1e2a4a',
    'accent_gold':   '#e8b339',
    'accent_gold_lt':'#f0d060',
    'accent_orange': '#e94560',
    'text_primary':  '#eaeaea',
    'text_secondary':'#a0a0b8',
    'text_muted':    '#6a6a80',
    'success':       '#00b894',
    'danger':        '#e94560',
    'warning':       '#fdcb6e',
    'info':          '#74b9ff',
    'border':        '#2a2a4a',
    'hover':         '#1e3a6e',
}

# ═══════════════════════════════════════════════════════════
# PROCESS CATEGORIES
# ═══════════════════════════════════════════════════════════
PROCESS_DB = {
    "OBS Studio": {
        "priority": 1,
        "color": "#74b9ff",
        "processes": [
            "obs64", "obs32",
        ],
        "description": "OBS Studio 主程序"
    },
    "OBS 子进程": {
        "priority": 2,
        "color": "#a29bfe",
        "processes": [
            "obs-browser-page", "obs-virtualcam",
            "obs-ffmpeg-mux", "obs-text", "obs-websocket",
        ],
        "description": "浏览器源、虚拟摄像头、编码器等"
    },
    "ASUS 全家桶": {
        "priority": 3,
        "color": "#fd79a8",
        "processes": [
            "asus_framework", "asus_nodejs_web_framework",
            "ArmouryCrate", "ArmouryCrate.Service",
            "ArmouryCrate.UserSessionHelper",
            "ArmouryHtmlDebugServer", "ArmourySocketServer",
            "ROGLiveService", "ASUSSmartDisplayControl",
            "ASUSSoftwareManager", "ASUSLinkNear", "ASUSLinkRemote",
            "ASUSSwitch", "ASUSOptimization",
            "AsusCertService", "AsusAppService",
            "AsusFanControlService",
            "GameSDK", "GameSDKService",
            "atkexComSvc", "NoiseCancelingEngine",
            "AcPowerNotification",
            "extensionCardHal_x86", "Aac3572MbHal_x86",
            "Aac3572DramHal_x86", "AacKingstonDramHal_x64",
            "AacKingstonDramHal_x86", "TrafficMonitor_ToastService",
        ],
        "description": "ASUS Armoury Crate & 硬件驱动 - 常阻塞OBS安装"
    },
    "流媒体 & 录制工具": {
        "priority": 4,
        "color": "#ff7675",
        "processes": [
            "Streamlabs", "StreamlabsOBS", "StreamlabsDesktop",
            "vMix64", "vMix",
            "XSplit", "XSplitBroadcaster", "XSplitGamecaster",
            "TwitchStudio", "NDI",
        ],
        "description": "可能冲突的直播/录制软件"
    },
    "游戏覆盖 & 录制": {
        "priority": 5,
        "color": "#fdcb6e",
        "processes": [
            "DiscordOverlay",
            "GameOverlayUI", "steamwebhelper",
            "RTSS", "RTSSHooksLoader64", "MSIAfterburner",
            "Overwolf", "OverwolfLauncher",
            "MedalEncoder", "Medal", "Outplayed",
            "NVIDIA Share", "nvcontainer", "NvTelemetryContainer",
        ],
        "description": "游戏覆盖层 / 截图 / 录制工具"
    },
    "硬件外设": {
        "priority": 6,
        "color": "#00b894",
        "processes": [
            "ElgatoCameraHub", "ElgatoControlCenter", "ElgatoWaveLink",
            "NahimicSvc64", "NahimicSvc32", "NahimicService",
            "NVIDIA Broadcast", "NVIDIABroadcast",
            "Voicemeeter", "VB-Audio",
        ],
        "description": "采集卡 / 音频处理器"
    },
}

ALWAYS_SCAN = [
    "obs64", "obs32", "asus_framework", "armourycrate",
    "streamlabs", "xsplit", "vmix64", "elgato",
]


def get_app_path():
    """Get app directory (works for both script and frozen EXE)"""
    if getattr(sys, 'frozen', False):
        # PyInstaller extracts to sys._MEIPASS
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def load_icon():
    """Load and return the app icon"""
    icon_path = get_app_path() / "logo.png"
    if HAS_PIL and icon_path.exists():
        try:
            img = Image.open(icon_path)
            return ImageTk.PhotoImage(img.resize((64, 64), Image.LANCZOS))
        except Exception:
            pass
    return None


# ═══════════════════════════════════════════════════════════
# BACKEND FUNCTIONS
# ═══════════════════════════════════════════════════════════

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    """Re-launch as admin"""
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            f'"{__file__}"' if not getattr(sys, 'frozen', False) else f'"{sys.executable}"',
            None, 1
        )
        return True
    return False


def scan_processes():
    """
    Scan all running processes and categorize them.
    Returns: dict of {category_name: [(pid, name, cmdline), ...]}
    """
    results = {}
    scanned = set()

    try:
        import wmi
        c = wmi.WMI()
        all_procs = {}

        for proc in c.Win32_Process():
            name = proc.Name.lower().replace('.exe', '') if proc.Name else ''
            all_procs[name] = (proc.ProcessId, proc.Name, proc.CommandLine or '')

    except ImportError:
        # Fallback: use tasklist
        try:
            output = subprocess.check_output(
                ['tasklist', '/FO', 'CSV', '/NH'],
                encoding='gbk', errors='replace'
            )
            for line in output.strip().split('\n'):
                parts = line.replace('"', '').split(',')
                if len(parts) >= 2:
                    name = parts[0].strip().lower()
                    pid = int(parts[1].strip())
                    all_procs[name] = (pid, parts[0].strip(), '')
        except Exception:
            pass

    # Scan ASUS node.exe by command line
    if 'wmi' in sys.modules:
        try:
            c = sys.modules['wmi'].WMI()
            for proc in c.Win32_Process(Name='node.exe'):
                cmd = (proc.CommandLine or '').lower()
                path = (proc.ExecutablePath or '').lower()
                if any(kw in cmd or kw in path for kw in ['asus', 'armoury', 'rog', 'gamesdk', 'aura']):
                    all_procs['asus_nodejs_web_framework'] = (
                        proc.ProcessId, 'node.exe', proc.CommandLine or ''
                    )
        except Exception:
            pass
    else:
        # Fallback: use wmic
        try:
            output = subprocess.check_output(
                ['wmic', 'process', 'where', 'name="node.exe"', 'get', 'ProcessId,CommandLine', '/format:csv'],
                encoding='gbk', errors='replace'
            )
            for line in output.strip().split('\n')[1:]:
                parts = line.strip().split(',')
                if len(parts) >= 2 and any(
                    kw in line.lower() for kw in ['asus', 'armoury', 'rog', 'gamesdk', 'aura']
                ):
                    try:
                        pid = int(parts[-2])
                        all_procs['asus_nodejs_web_framework'] = (pid, 'node.exe', line)
                    except ValueError:
                        pass
        except Exception:
            pass

    # Categorize
    for category, data in PROCESS_DB.items():
        found = []
        for proc_name in data['processes']:
            key = proc_name.lower()
            if key in all_procs and key not in scanned:
                found.append(all_procs[key])
                scanned.add(key)
        if found:
            results[category] = found

    # Check for "Other" - catch any remaining OBS-related
    other = []
    for name, info in all_procs.items():
        if name not in scanned:
            if any(kw in name for kw in ['obs', 'stream', 'record', 'capture', 'webcam']):
                other.append(info)
                scanned.add(name)
    if other:
        results["其他相关进程"] = other

    return results


def kill_process_by_name(name):
    """Kill a process by name"""
    try:
        subprocess.run(
            ['taskkill', '/F', '/IM', name],
            capture_output=True, timeout=10
        )
        return True, f"已终止: {name}"
    except Exception as e:
        return False, f"失败: {name} - {e}"


def kill_process_by_pid(pid):
    """Kill a process by PID"""
    try:
        subprocess.run(
            ['taskkill', '/F', '/PID', str(pid)],
            capture_output=True, timeout=10
        )
        return True, f"已终止 PID:{pid}"
    except Exception as e:
        return False, f"失败 PID:{pid} - {e}"


def kill_process_tree(name):
    """Kill process and all children"""
    try:
        subprocess.run(
            ['taskkill', '/F', '/T', '/IM', name],
            capture_output=True, timeout=10
        )
        return True, f"已终止进程树: {name}"
    except Exception as e:
        return False, f"失败: {name} - {e}"


def get_obs_config_dir():
    return Path(os.environ.get('APPDATA', '')) / 'obs-studio'


def reset_obs_config():
    """Backup and reset OBS configuration"""
    obs_dir = get_obs_config_dir()
    if not obs_dir.exists():
        return False, "未找到 OBS 配置目录", None

    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_dir = Path(os.environ['APPDATA']) / f'obs-studio-backup-{ts}'

    try:
        # Backup
        import shutil
        shutil.copytree(obs_dir, backup_dir)
        # Remove
        shutil.rmtree(obs_dir)
        return True, f"配置已重置！备份在: {backup_dir}", str(backup_dir)
    except Exception as e:
        return False, f"重置失败: {e}", None


# ═══════════════════════════════════════════════════════════
# OBS PLUGIN & FIX FUNCTIONS
# ═══════════════════════════════════════════════════════════

# Known OBS built-in plugins (ships with OBS Studio)
OBS_BUILTIN_PLUGINS = {
    'coreaudio-encoder', 'decklink-captions', 'decklink-output-ui',
    'image-source', 'obs-browser', 'obs-ffmpeg', 'obs-filters',
    'obs-outputs', 'obs-qsv11', 'obs-text', 'obs-transitions',
    'obs-vst', 'obs-webrtc', 'obs-websocket', 'obs-x264',
    'text-freetype2', 'vlc-video', 'win-capture', 'win-dshow',
    'win-wasapi',
}

class PluginInfo:
    """Represents a detected OBS plugin"""
    def __init__(self, name, path, size, location_type, install_time=None, is_builtin=False):
        self.name = name          # e.g. "obs-curve-grade"
        self.filename = path.name  # e.g. "obs-curve-grade.dll"
        self.path = path           # full Path
        self.size = size           # bytes
        self.size_str = self._fmt_size(size)
        self.location_type = location_type  # 'system', 'user', 'portable'
        self.location_label = {
            'system': '📁 OBS安装目录',
            'user': '👤 用户数据目录',
            'portable': '📦 便携版目录',
        }.get(location_type, location_type)
        self.install_time = install_time  # datetime or None
        self.install_time_str = (
            install_time.strftime('%Y-%m-%d %H:%M') if install_time else '未知'
        )
        self.is_builtin = is_builtin  # True if OBS system plugin
        self._scan_extra_files()  # discover .pdb, data dirs, etc.

    @staticmethod
    def _fmt_size(size):
        if size >= 1048576:
            return f'{size / 1048576:.1f} MB'
        elif size >= 1024:
            return f'{size / 1024:.1f} KB'
        return f'{size} B'

    def _scan_extra_files(self):
        """Discover all files/folders associated with this plugin"""
        extras = []

        # 1. .pdb debug symbols (same directory as DLL)
        pdb = self.path.parent / f'{self.name}.pdb'
        if pdb.exists():
            extras.append(pdb)

        # 2. Data folder in same directory (e.g. obs-plugins/64bit/<plugin-name>/)
        local_data = self.path.parent / self.name
        if local_data.exists() and local_data.is_dir():
            extras.append(local_data)

        # 3. Plugin data directory: obs-studio/data/obs-plugins/<plugin-name>/
        # Path: .../obs-studio/obs-plugins/64bit/xxx.dll -> .../obs-studio/data/obs-plugins/xxx/
        try:
            obs_root = self.path.parent.parent.parent  # up to obs-studio/
            global_data = obs_root / 'data' / 'obs-plugins' / self.name
            if global_data.exists() and global_data.is_dir():
                extras.append(global_data)
        except Exception:
            pass

        self.extra_files = extras
        self.extra_count = len(extras)
        self.extra_size = 0
        for f in extras:
            try:
                if f.is_dir():
                    self.extra_size += sum(
                        p.stat().st_size for p in f.rglob('*') if p.is_file()
                    )
                else:
                    self.extra_size += f.stat().st_size
            except Exception:
                pass
        self.extra_size_str = self._fmt_size(self.extra_size)

    def delete(self):
        """Delete this plugin DLL and all associated files"""
        results = []

        # Ensure extras are scanned
        if not hasattr(self, 'extra_files'):
            self._scan_extra_files()

        # Delete main DLL
        try:
            self.path.unlink()
            results.append(('ok', f'已删除: {self.filename}'))
        except Exception as e:
            results.append(('err', f'删除失败 {self.filename}: {e}'))
            return results

        # Delete associated files
        import shutil
        for f in self.extra_files:
            try:
                if f.is_dir():
                    shutil.rmtree(f)
                    results.append(('ok', f'已清除数据目录: {f.name}'))
                else:
                    f.unlink()
                    results.append(('ok', f'已删除关联文件: {f.name}'))
            except Exception as e:
                results.append(('warn', f'关联文件清除失败 {f.name}: {e}'))

        return results


def find_obs_install_dirs():
    """
    Find all OBS Studio installation directories.
    Returns list of (path, location_type) tuples.
    """
    found = []
    
    # 1. Check registry
    try:
        import winreg
        for hive, key_path in [
            (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\OBS Studio'),
            (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\OBS Studio'),
            (winreg.HKEY_CURRENT_USER, r'SOFTWARE\OBS Studio'),
        ]:
            try:
                key = winreg.OpenKey(hive, key_path)
                try:
                    val, _ = winreg.QueryValueEx(key, '')
                    if val:
                        p = Path(val)
                        if p.exists() and p not in [f[0] for f in found]:
                            found.append((p, 'system'))
                except OSError:
                    pass
                winreg.CloseKey(key)
            except OSError:
                pass
    except ImportError:
        pass
    
    # 2. Check common install paths
    common_paths = [
        Path('C:/Program Files/obs-studio'),
        Path('C:/Program Files (x86)/obs-studio'),
        Path('D:/APP/obs-studio'),
        Path('D:/obs-studio'),
        Path(os.path.expandvars('%LOCALAPPDATA%/obs-studio')),
    ]
    for p in common_paths:
        if p.exists() and p not in [f[0] for f in found]:
            obs_exe = p / 'bin' / '64bit' / 'obs64.exe'
            if not obs_exe.exists():
                obs_exe = p / 'obs64.exe'
            if obs_exe.exists():
                found.append((p, 'system'))
    
    # 3. Check if obs64.exe in PATH
    try:
        import shutil as _shutil
        obs_path = _shutil.which('obs64.exe')
        if obs_path:
            p = Path(obs_path).parent.parent  # go up from bin/64bit
            if p.exists() and p not in [f[0] for f in found]:
                found.append((p, 'system'))
    except Exception:
        pass
    
    return found


def scan_obs_plugins():
    """
    Scan all OBS plugin locations.
    Returns list of PluginInfo objects.
    """
    plugins = []
    seen = set()  # dedup by filename
    
    def add_dlls(directory, location_type):
        if not directory.exists():
            return
        for dll in sorted(directory.glob('*.dll')):
            if dll.name.lower() in seen:
                continue
            seen.add(dll.name.lower())
            try:
                stat = dll.stat()
                size = stat.st_size
                install_time = datetime.fromtimestamp(stat.st_mtime)
            except Exception:
                size = 0
                install_time = None
            is_builtin = dll.stem.lower() in OBS_BUILTIN_PLUGINS
            plugins.append(PluginInfo(
                name=dll.stem,
                path=dll,
                size=size,
                location_type=location_type,
                install_time=install_time,
                is_builtin=is_builtin
            ))
    
    # System install plugins
    for install_dir, loc_type in find_obs_install_dirs():
        for arch in ['64bit', '32bit']:
            add_dlls(install_dir / 'obs-plugins' / arch, 'system')
    
    # User plugins (AppData)
    roaming = Path(os.environ.get('APPDATA', '')) / 'obs-studio'
    user_plugins = roaming / 'plugins'
    if user_plugins.exists():
        for dll_dir in user_plugins.rglob('*'):
            if dll_dir.is_dir():
                for dll in sorted(dll_dir.glob('*.dll')):
                    if dll.name.lower() in seen:
                        continue
                    seen.add(dll.name.lower())
                    try:
                        stat = dll.stat()
                        size = stat.st_size
                        install_time = datetime.fromtimestamp(stat.st_mtime)
                    except Exception:
                        size = 0
                        install_time = None
                    is_builtin = dll.stem.lower() in OBS_BUILTIN_PLUGINS
                    plugins.append(PluginInfo(
                        name=dll.stem,
                        path=dll,
                        size=size,
                        location_type='user',
                        install_time=install_time,
                        is_builtin=is_builtin
                    ))
    
    return plugins


def delete_plugins(plugin_list):
    """
    Delete multiple plugins.
    Returns (success_count, fail_count, messages_list)
    """
    success = 0
    fail = 0
    messages = []
    
    for plugin in plugin_list:
        results = plugin.delete()
        for status, msg in results:
            if status == 'ok':
                success += 1
            else:
                fail += 1
            messages.append(msg)
    
    return success, fail, messages


def get_obs_cache_dirs():
    """Find OBS cache directories to clean"""
    caches = []
    roaming = Path(os.environ.get('APPDATA', '')) / 'obs-studio'
    
    # Shader cache
    shader_cache = roaming / 'shader-cache'
    if shader_cache.exists():
        caches.append(('Shader 缓存', shader_cache))
    
    # Plugin config cache
    plugin_config = roaming / 'plugin_config'
    if plugin_config.exists():
        caches.append(('插件配置缓存', plugin_config))
    
    # Crashes
    crashes = roaming / 'crashes'
    if crashes.exists():
        caches.append(('崩溃日志', crashes))
    
    return caches


def fix_obs_issues(log_callback=None, ask_config_reset=False, parent=None):
    """
    Comprehensive OBS fix function.
    
    Args:
        log_callback: callable(status, msg) for progress reporting
        ask_config_reset: if True, will prompt before config reset
        parent: parent window for dialogs
    
    Returns:
        dict with results summary
    """
    results = {
        'processes_killed': 0,
        'caches_cleared': 0,
        'config_reset': False,
        'config_backup': None,
        'warnings': [],
        'errors': [],
    }
    
    def log(status, msg):
        if log_callback:
            log_callback(msg, status)  # msg comes first, status is the tag
    
    # ─── Phase 1: Kill all OBS + interfering processes ───
    log('info', '═══ 第1步: 清理运行中的进程 ═══')
    
    obs_procs = ['obs64', 'obs32', 'obs-browser-page', 'obs-ffmpeg-mux']
    killed = 0
    for name in obs_procs:
        try:
            r = subprocess.run(
                ['taskkill', '/F', '/IM', f'{name}.exe'],
                capture_output=True, timeout=10
            )
            if r.returncode == 0:
                killed += 1
                log('ok', f'已终止 OBS 进程: {name}')
        except Exception as e:
            log('warn', f'终止 {name} 失败: {e}')
    
    results['processes_killed'] = killed
    time.sleep(1)  # Wait for processes to fully exit
    
    # ─── Phase 2: Clear caches ───
    log('info', '═══ 第2步: 清理缓存文件 ═══')
    
    import shutil as _shutil
    caches = get_obs_cache_dirs()
    cleared = 0
    for name, path in caches:
        try:
            _shutil.rmtree(path)
            cleared += 1
            log('ok', f'已清除: {name}')
        except Exception as e:
            log('warn', f'清除 {name} 失败: {e}')
    
    results['caches_cleared'] = cleared
    
    # ─── Phase 3: Check for problematic plugins ───
    log('info', '═══ 第3步: 检查插件冲突 ═══')
    
    plugins = scan_obs_plugins()
    
    # Known problematic patterns
    problematic = [
        'obs-virtualcam', 'win-capture-audio', 'obs-websocket',
        'obs-webrtc', 'advanced-scene-switcher', 'streamfx',
    ]
    
    found_problematic = []
    for p in plugins:
        for kw in problematic:
            if kw.lower() in p.name.lower():
                found_problematic.append(p.name)
                break
    
    if found_problematic:
        log('warn', f'发现可能有冲突的插件: {", ".join(found_problematic)}')
        log('info', '(可通过"插件管理"功能选择性删除)')
    else:
        log('ok', '未发现已知冲突插件')
    
    # ─── Phase 4: Config reset (with backup) ───
    if ask_config_reset and parent:
        do_reset = messagebox.askyesno(
            "配置重置",
            "是否同时重置 OBS 配置？\n\n"
            "• 会自动备份当前配置\n"
            "• 下次启动OBS将运行设置向导\n\n"
            "如果OBS因配置损坏而崩溃，建议重置。",
            parent=parent
        )
    else:
        do_reset = True  # Default for non-interactive mode
    
    if do_reset:
        log('info', '═══ 第4步: 备份并重置配置 ═══')
        obs_dir = get_obs_config_dir()
        if obs_dir.exists():
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            backup_dir = Path(os.environ['APPDATA']) / f'obs-studio-backup-fix-{ts}'
            try:
                _shutil.copytree(obs_dir, backup_dir)
                _shutil.rmtree(obs_dir)
                results['config_reset'] = True
                results['config_backup'] = str(backup_dir)
                log('ok', f'配置已备份到: {backup_dir}')
                log('ok', '配置已重置为默认值')
            except Exception as e:
                results['errors'].append(f'配置重置失败: {e}')
                log('err', f'配置重置失败: {e}')
        else:
            log('info', '未找到OBS配置目录，跳过重置')
    
    # ─── Summary ───
    log('info', '═══ 修复完成! ═══')
    log('ok', f'清理进程: {results["processes_killed"]} 个')
    log('ok', f'清理缓存: {results["caches_cleared"]} 项')
    
    if results['config_reset']:
        log('ok', f'配置已重置 (备份: {results["config_backup"]})')
    
    if results['errors']:
        log('err', f'遇到 {len(results["errors"])} 个错误')
    
    return results


# ═══════════════════════════════════════════════════════════
# MODERN UI COMPONENTS
# ═══════════════════════════════════════════════════════════

class ModernFrame(tk.Frame):
    """A card-style frame with optional header"""
    def __init__(self, parent, title=None, **kwargs):
        bg = kwargs.pop('bg', COLORS['bg_panel'])
        super().__init__(parent, bg=bg, **kwargs)
        self.title_text = title
        
        if title:
            self.header = tk.Frame(self, bg=bg)
            self.header.pack(fill='x', padx=15, pady=(8, 3))
            
            self.title_label = tk.Label(
                self.header, text=title,
                font=('Microsoft YaHei UI', 13, 'bold'),
                fg=COLORS['accent_gold'], bg=bg
            )
            self.title_label.pack(side='left')
            
            self.header_sep = tk.Frame(self, height=1, bg=COLORS['border'])
            self.header_sep.pack(fill='x', padx=20)


class ModernButton(tk.Button):
    """Styled button with hover effects"""
    def __init__(self, parent, text, command=None, variant='primary', **kwargs):
        variants = {
            'primary':  (COLORS['accent_gold'], COLORS['bg_dark'], COLORS['accent_gold_lt']),
            'danger':   (COLORS['danger'], '#fff', '#ff6b81'),
            'success':  (COLORS['success'], '#fff', '#55efc4'),
            'info':     (COLORS['info'], COLORS['bg_dark'], '#a0d2ff'),
            'ghost':    (COLORS['bg_panel'], COLORS['text_primary'], COLORS['bg_card']),
        }
        bg, fg, hover = variants.get(variant, variants['primary'])
        
        super().__init__(
            parent, text=text, command=command,
            bg=bg, fg=fg,
            font=('Microsoft YaHei UI', 10, 'bold'),
            relief='flat', bd=0, cursor='hand2',
            padx=18, pady=8,
            **kwargs
        )
        self._hover_color = hover
        self._normal_color = bg
        self._fg = fg
        
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.configure(highlightthickness=0, activebackground=hover)
    
    def _on_enter(self, e):
        self.configure(bg=self._hover_color)
    
    def _on_leave(self, e):
        self.configure(bg=self._normal_color)


class SearchBar(tk.Frame):
    """Search input with icon"""
    def __init__(self, parent, on_change=None, **kwargs):
        super().__init__(parent, bg=COLORS['bg_dark'], **kwargs)
        self.on_change = on_change
        
        # Search container
        self.container = tk.Frame(self, bg=COLORS['bg_input'])
        self.container.pack(fill='x', padx=0, pady=0)
        
        # Search icon (magnifier)
        self.icon_label = tk.Label(
            self.container, text='🔍',
            font=('Segoe UI Emoji', 14),
            fg=COLORS['text_muted'], bg=COLORS['bg_input']
        )
        self.icon_label.pack(side='left', padx=(12, 5), pady=3)
        
        # Entry
        self.entry = tk.Entry(
            self.container,
            font=('Microsoft YaHei UI', 11),
            bg=COLORS['bg_input'], fg=COLORS['text_primary'],
            insertbackground=COLORS['accent_gold'],
            relief='flat', bd=0,
        )
        self.entry.pack(side='left', fill='x', expand=True, padx=(0, 10), pady=1)
        self.entry.bind('<KeyRelease>', self._on_key)
        self.entry.insert(0, '搜索进程名称...')
        self.entry.bind('<FocusIn>', self._on_focus_in)
        self.entry.bind('<FocusOut>', self._on_focus_out)
        
        # Clear button
        self.clear_btn = tk.Label(
            self.container, text='✕',
            font=('Segoe UI Emoji', 12),
            fg=COLORS['text_muted'], bg=COLORS['bg_input'],
            cursor='hand2'
        )
        self.clear_btn.pack(side='right', padx=(0, 12))
        self.clear_btn.bind('<Button-1>', self._clear)
    
    def _on_key(self, e):
        if self.on_change:
            self.on_change(self.entry.get())
    
    def _on_focus_in(self, e):
        if self.entry.get() == '搜索进程名称...':
            self.entry.delete(0, 'end')
            self.entry.configure(fg=COLORS['text_primary'])
    
    def _on_focus_out(self, e):
        if not self.entry.get():
            self.entry.insert(0, '搜索进程名称...')
            self.entry.configure(fg=COLORS['text_muted'])
    
    def _clear(self, e):
        self.entry.delete(0, 'end')
        self.entry.focus_set()
        if self.on_change:
            self.on_change('')
    
    def get(self):
        val = self.entry.get()
        return '' if val == '搜索进程名称...' else val


class ProcessCard(tk.Frame):
    """Individual process card in the list"""
    def __init__(self, parent, pid, name, cmdline='', category_color='#888', **kwargs):
        super().__init__(parent, bg=COLORS['bg_card'], cursor='hand2', **kwargs)
        self.pid = pid
        self.name = name
        
        # Left color bar
        self.color_bar = tk.Frame(self, width=4, bg=category_color)
        self.color_bar.pack(side='left', fill='y')
        
        # Content
        self.content = tk.Frame(self, bg=COLORS['bg_card'])
        self.content.pack(side='left', fill='both', expand=True, padx=12, pady=8)
        
        # Name + PID
        self.name_label = tk.Label(
            self.content, text=name,
            font=('Consolas', 10, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card'],
            anchor='w'
        )
        self.name_label.pack(anchor='w')
        
        self.pid_label = tk.Label(
            self.content, text=f'PID: {pid}',
            font=('Consolas', 8),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card'],
            anchor='w'
        )
        self.pid_label.pack(anchor='w')
        
        if cmdline:
            self.cmd_label = tk.Label(
                self.content,
                text=cmdline[:80] + ('...' if len(cmdline) > 80 else ''),
                font=('Consolas', 7),
                fg=COLORS['text_muted'], bg=COLORS['bg_card'],
                anchor='w', wraplength=400
            )
            self.cmd_label.pack(anchor='w')
        
        # Kill button
        self.kill_btn = tk.Label(
            self, text='⏻  终止',
            font=('Microsoft YaHei UI', 9, 'bold'),
            fg=COLORS['danger'], bg=COLORS['bg_card'],
            cursor='hand2', padx=10
        )
        self.kill_btn.pack(side='right', padx=(0, 10))
        self.kill_btn.bind('<Button-1>', lambda e: self._kill())
        
        # Hover effect
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.name_label.bind('<Enter>', self._on_enter)
        self.name_label.bind('<Leave>', self._on_leave)
    
    def _on_enter(self, e):
        self.configure(bg=COLORS['hover'])
        self.content.configure(bg=COLORS['hover'])
        self.name_label.configure(bg=COLORS['hover'])
        self.pid_label.configure(bg=COLORS['hover'])
        if hasattr(self, 'cmd_label'):
            self.cmd_label.configure(bg=COLORS['hover'])
        self.kill_btn.configure(bg=COLORS['hover'])
    
    def _on_leave(self, e):
        self.configure(bg=COLORS['bg_card'])
        self.content.configure(bg=COLORS['bg_card'])
        self.name_label.configure(bg=COLORS['bg_card'])
        self.pid_label.configure(bg=COLORS['bg_card'])
        if hasattr(self, 'cmd_label'):
            self.cmd_label.configure(bg=COLORS['bg_card'])
        self.kill_btn.configure(bg=COLORS['bg_card'])
    
    def _kill(self):
        """Handle kill button click"""
        if messagebox.askyesno(
            "确认终止", f"确定要终止 {self.name} (PID: {self.pid}) 吗？",
            parent=self
        ):
            success, msg = kill_process_by_pid(self.pid)
            if success:
                self.configure(bg=COLORS['success'])
                self.color_bar.configure(bg=COLORS['success'])
                self.kill_btn.configure(text='✓ 已终止', fg=COLORS['success'])
                # Remove after delay
                self.after(800, self.destroy)
            else:
                messagebox.showerror("错误", msg, parent=self)


class CategorySection(tk.Frame):
    """Collapsible category section"""
    def __init__(self, parent, category_name, category_data, proc_list, **kwargs):
        super().__init__(parent, bg=COLORS['bg_dark'], **kwargs)
        self.category_name = category_name
        self.category_data = category_data
        self.proc_list = proc_list
        self.is_expanded = True
        
        color = category_data['color']
        
        # Header
        self.header = tk.Frame(self, bg=COLORS['bg_panel'], cursor='hand2')
        self.header.pack(fill='x', pady=(5, 0))
        
        # Expand/collapse arrow
        self.arrow_label = tk.Label(
            self.header, text='▼',
            font=('Segoe UI Emoji', 10),
            fg=color, bg=COLORS['bg_panel'],
            width=2
        )
        self.arrow_label.pack(side='left', padx=(8, 3), pady=4)
        
        # Category name
        self.name_label = tk.Label(
            self.header, text=category_name,
            font=('Microsoft YaHei UI', 11, 'bold'),
            fg=color, bg=COLORS['bg_panel']
        )
        self.name_label.pack(side='left', pady=5)
        
        # Description
        self.desc_label = tk.Label(
            self.header, text=category_data.get('description', ''),
            font=('Microsoft YaHei UI', 8),
            fg=COLORS['text_muted'], bg=COLORS['bg_panel']
        )
        self.desc_label.pack(side='left', padx=(8, 0), pady=5)
        
        # Spacer
        tk.Frame(self.header, bg=COLORS['bg_panel']).pack(side='left', fill='x', expand=True)
        
        # Count badge
        self.count_label = tk.Label(
            self.header, text=f'{len(proc_list)} 个进程',
            font=('Consolas', 9),
            fg=COLORS['bg_dark'], bg=color,
            padx=8, pady=2
        )
        self.count_label.pack(side='right', padx=8, pady=5)
        
        # Kill all button
        self.kill_all_btn = ModernButton(
            self.header, '一键终止此组',
            command=self._kill_all,
            variant='danger'
        )
        self.kill_all_btn.pack(side='right', padx=(0, 3), pady=3)
        
        # Bind click to expand/collapse
        for widget in [self.header, self.arrow_label, self.name_label, self.desc_label]:
            widget.bind('<Button-1>', self._toggle)
        
        # Content container
        self.content = tk.Frame(self, bg=COLORS['bg_dark'])
        self.content.pack(fill='x')
        
        # Process cards
        self.cards = []
        for pid, name, cmdline in proc_list:
            card = ProcessCard(self.content, pid, name, cmdline, color)
            card.pack(fill='x', pady=1, padx=5)
            self.cards.append(card)
    
    def _toggle(self, e=None):
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            self.content.pack(fill='x')
            self.arrow_label.configure(text='▼')
        else:
            self.content.pack_forget()
            self.arrow_label.configure(text='▶')
    
    def _kill_all(self):
        names = set(c.name for c in self.cards if c.winfo_exists())
        count = len(names)
        if count == 0:
            return
        
        if not messagebox.askyesno(
            "确认操作",
            f"确定要终止「{self.category_name}」下的 {count} 个进程吗？\n\n"
            f"进程列表:\n" + "\n".join(f"  • {n}" for n in sorted(names)),
            parent=self
        ):
            return
        
        for card in self.cards[:]:
            if card.winfo_exists():
                success, msg = kill_process_by_pid(card.pid)
                card.after(100, card.destroy)
        
        self.after(500, lambda: messagebox.showinfo(
            "操作完成", f"已终止 {self.category_name} 下的进程。", parent=self
        ))
    
    def filter_processes(self, search_term):
        """Filter cards by search term"""
        term = search_term.lower()
        visible = False
        for card in self.cards:
            if term and term not in card.name.lower() and term not in str(card.pid):
                card.pack_forget()
            else:
                card.pack(fill='x', pady=1, padx=5)
                visible = True
        
        if not visible and term:
            self.pack_forget()
        else:
            if term:
                self.pack(fill='x', pady=(0, 0))
            else:
                self.pack(fill='x', pady=(8, 0))


# ═══════════════════════════════════════════════════════════
# STATUS BAR
# ═══════════════════════════════════════════════════════════

class StatusBar(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS['bg_panel'], height=32, **kwargs)
        self.pack_propagate(False)
        
        # Admin status
        self.admin_label = tk.Label(
            self, text='🔒 管理员' if is_admin() else '⚠ 非管理员',
            font=('Microsoft YaHei UI', 9),
            fg=COLORS['success'] if is_admin() else COLORS['warning'],
            bg=COLORS['bg_panel']
        )
        self.admin_label.pack(side='left', padx=15, pady=4)
        
        # Status text
        self.status_label = tk.Label(
            self, text='就绪',
            font=('Microsoft YaHei UI', 9),
            fg=COLORS['text_secondary'], bg=COLORS['bg_panel']
        )
        self.status_label.pack(side='left', padx=10, pady=4)
        
        # Spacer
        tk.Frame(self, bg=COLORS['bg_panel']).pack(side='left', fill='x', expand=True)
        
        # Version
        self.version_label = tk.Label(
            self, text='v3.5 | 影视匠 OBS 管理工具箱',
            font=('Microsoft YaHei UI', 9),
            fg=COLORS['text_muted'], bg=COLORS['bg_panel']
        )
        self.version_label.pack(side='right', padx=15, pady=4)
    
    def set_status(self, text, color=None):
        self.status_label.configure(text=text, fg=color or COLORS['text_secondary'])


# ═══════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════

class OBSManagerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('影视匠 OBS 管理工具箱 v3.5')
        self.root.geometry('1000x680')
        self.root.minsize(800, 520)
        self.root.configure(bg=COLORS['bg_dark'])
        
        # Set icon
        self.app_icon = load_icon()
        if self.app_icon:
            self.root.iconphoto(True, self.app_icon)
        
        # Style ttk
        self._setup_ttk_style()
        
        # Sections
        self.sections = {}
        self.current_filter = ''
        
        # Build UI
        self._build_ui()
        
        # Auto-scan on startup
        self.root.after(500, self._refresh)
    
    def _setup_ttk_style(self):
        style = ttk.Style()
        if HAS_TTKB:
            style.theme_use('darkly')
        
        style.configure('TFrame', background=COLORS['bg_dark'])
        style.configure('TLabel', background=COLORS['bg_dark'], foreground=COLORS['text_primary'])
        style.configure('TButton', font=('Microsoft YaHei UI', 10))
    
    def _build_ui(self):
        # ─── HEADER ───
        header = tk.Frame(self.root, bg=COLORS['bg_panel'], height=80)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        # Logo area
        logo_frame = tk.Frame(header, bg=COLORS['bg_panel'])
        logo_frame.pack(side='left', padx=20, pady=10)
        
        if self.app_icon:
            self.logo_img_label = tk.Label(logo_frame, image=self.app_icon, bg=COLORS['bg_panel'])
            self.logo_img_label.pack(side='left', padx=(0, 12))
        
        logo_text_frame = tk.Frame(logo_frame, bg=COLORS['bg_panel'])
        logo_text_frame.pack(side='left')
        
        tk.Label(
            logo_text_frame, text='影视匠 OBS 管理工具箱',
            font=('Microsoft YaHei UI', 18, 'bold'),
            fg=COLORS['accent_gold'], bg=COLORS['bg_panel']
        ).pack(anchor='w')
        
        tk.Label(
            logo_text_frame, text='Professional OBS Process & Configuration Manager',
            font=('Microsoft YaHei UI', 9),
            fg=COLORS['text_muted'], bg=COLORS['bg_panel']
        ).pack(anchor='w')
        
        # Toolbar
        toolbar = tk.Frame(header, bg=COLORS['bg_panel'])
        toolbar.pack(side='right', padx=20, pady=15)
        
        self.refresh_btn = ModernButton(
            toolbar, '🔄 刷新进程列表',
            command=self._refresh, variant='ghost'
        )
        self.refresh_btn.pack(side='left', padx=4)
        
        self.tools_btn = ModernButton(
            toolbar, '⚙ 配置工具',
            command=self._show_config_tools, variant='ghost'
        )
        self.tools_btn.pack(side='left', padx=4)
        
        # ─── MAIN CONTENT ───
        main = tk.Frame(self.root, bg=COLORS['bg_dark'])
        main.pack(fill='both', expand=True, padx=15, pady=(5, 0))
        
        # ---- LEFT PANEL: Process list ----
        self.left_panel = tk.Frame(main, bg=COLORS['bg_dark'])
        self.left_panel.pack(side='left', fill='both', expand=True)
        
        # Search
        search_frame = tk.Frame(self.left_panel, bg=COLORS['bg_dark'])
        search_frame.pack(fill='x', pady=(0, 5))
        
        self.search_bar = SearchBar(search_frame, on_change=self._on_search)
        self.search_bar.pack(side='left', fill='x', expand=True)
        
        # Stats row
        self.stats_bar = tk.Frame(self.left_panel, bg=COLORS['bg_dark'])
        self.stats_bar.pack(fill='x', pady=(0, 5))
        
        self.stats_total = tk.Label(
            self.stats_bar, text='正在扫描...',
            font=('Microsoft YaHei UI', 9),
            fg=COLORS['text_muted'], bg=COLORS['bg_dark']
        )
        self.stats_total.pack(side='left')
        
        # Process list (scrollable)
        self.canvas_frame = tk.Frame(self.left_panel, bg=COLORS['bg_dark'])
        self.canvas_frame.pack(fill='both', expand=True)
        
        self.canvas = tk.Canvas(
            self.canvas_frame, bg=COLORS['bg_dark'],
            highlightthickness=0, bd=0
        )
        self.scrollbar = ttk.Scrollbar(self.canvas_frame, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.process_container = tk.Frame(self.canvas, bg=COLORS['bg_dark'])
        self.canvas_window = self.canvas.create_window((0, 0), window=self.process_container, anchor='nw')
        
        self.scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        
        # Bind resize
        self.process_container.bind('<Configure>', self._on_container_configure)
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        
        # Mousewheel scrolling
        self.canvas.bind('<Enter>', self._bind_mousewheel)
        self.canvas.bind('<Leave>', self._unbind_mousewheel)
        
        # ---- RIGHT PANEL: Quick actions ----
        right_panel = tk.Frame(main, bg=COLORS['bg_dark'], width=280)
        right_panel.pack(side='right', fill='y', padx=(15, 0))
        right_panel.pack_propagate(False)
        
        # Quick Actions Card
        actions_card = ModernFrame(right_panel, title='🚀 快捷操作')
        actions_card.pack(fill='x', pady=(0, 5))
        actions_body = tk.Frame(actions_card, bg=COLORS['bg_panel'])
        actions_body.pack(fill='x', padx=18, pady=(3, 10))
        
        self.action_btns = []
        
        btn_data = [
            ('🗑  一键清退全部', 'danger', self._kill_all_everything,
             '终止所有已发现的干扰进程'),
            ('🔧 仅清理 ASUS', 'info', self._kill_asu_sonly,
             '专门针对 ASUS 进程（OBS安装前用）'),
            ('🔄 重置 OBS 配置', 'warning', self._reset_config,
             '备份当前配置后恢复默认设置'),
            ('⚡ 一键清退+重置', 'primary', self._one_click,
             '先清退所有进程，再重置配置'),
            ('🩺 一键修复 OBS 问题', 'success', self._fix_all_issues,
             '综合诊断：清进程、清缓存、修复配置、检查插件'),
            ('📦 插件管理', 'info', self._show_plugin_manager,
             '检测、列出、选择性删除 OBS 插件'),
        ]
        
        for text, var, cmd, tooltip in btn_data:
            btn = ModernButton(actions_body, text, command=cmd, variant=var)
            btn.pack(fill='x', pady=2)
            self.action_btns.append(btn)
            
            tt = ToolTip(btn, tooltip)
        
        # Log panel
        log_card = ModernFrame(right_panel, title='📋 操作日志')
        log_card.pack(fill='both', expand=True)
        log_body = tk.Frame(log_card, bg=COLORS['bg_panel'])
        log_body.pack(fill='both', expand=True, padx=18, pady=(3, 10))
        
        self.log_text = scrolledtext.ScrolledText(
            log_body,
            font=('Consolas', 9),
            bg=COLORS['bg_dark'],
            fg=COLORS['text_primary'],
            insertbackground=COLORS['accent_gold'],
            relief='flat', bd=0,
            wrap='word',
            height=8
        )
        self.log_text.pack(fill='both', expand=True)
        self.log_text.configure(state='disabled')
        
        self._log('影视匠 OBS 管理工具箱 已启动')
        self._log('等待进程扫描...')
        
        # ─── STATUS BAR ───
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(side='bottom', fill='x')
    
    def _on_container_configure(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
    
    def _on_canvas_configure(self, e):
        self.canvas.itemconfig(self.canvas_window, width=e.width)
    
    def _bind_mousewheel(self, e):
        self.canvas.bind_all('<MouseWheel>', self._on_mousewheel)
    
    def _unbind_mousewheel(self, e):
        self.canvas.unbind_all('<MouseWheel>')
    
    def _on_mousewheel(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
    
    def _log(self, msg, tag=None):
        """Append to log"""
        self.log_text.configure(state='normal')
        ts = datetime.now().strftime('%H:%M:%S')
        color = ''
        if tag == 'ok':
            color = 'green'
        elif tag == 'err':
            color = 'red'
        elif tag == 'warn':
            color = 'orange'
        
        if color:
            self.log_text.tag_config(color, foreground=color)
            self.log_text.insert('end', f'[{ts}] ', color)
            self.log_text.insert('end', f'{msg}\n', color)
        else:
            self.log_text.insert('end', f'[{ts}] {msg}\n')
        
        self.log_text.see('end')
        self.log_text.configure(state='disabled')
    
    def _on_search(self, term):
        """Filter process list by search term"""
        self.current_filter = term.strip()
        for section in self.sections.values():
            section.filter_processes(self.current_filter)
    
    def _set_loading(self, loading=True):
        """Update UI state during operations"""
        state = 'disabled' if loading else 'normal'
        for btn in self.action_btns:
            btn.configure(state=state)
        self.refresh_btn.configure(state=state)
        if loading:
            self.status_bar.set_status('⏳ 操作进行中...', COLORS['warning'])
        else:
            self.status_bar.set_status('就绪')
    
    # ─── CORE ACTIONS ───
    
    def _refresh(self):
        """Scan and display processes"""
        def worker():
            self.root.after(0, lambda: self.status_bar.set_status('🔍 正在扫描进程...', COLORS['info']))
            self.root.after(0, lambda: self._log('开始扫描系统进程...'))
            
            results = scan_processes()
            
            self.root.after(0, lambda: self._display_results(results))
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _display_results(self, results):
        """Display categorized process results"""
        # Clear old
        for widget in self.process_container.winfo_children():
            widget.destroy()
        self.sections.clear()
        
        total_procs = sum(len(v) for v in results.values())
        
        if total_procs == 0:
            # Empty state
            empty_frame = tk.Frame(self.process_container, bg=COLORS['bg_dark'])
            empty_frame.pack(fill='x', pady=30)
            
            tk.Label(
                empty_frame, text='✅',
                font=('Segoe UI Emoji', 48),
                fg=COLORS['success'], bg=COLORS['bg_dark']
            ).pack()
            
            tk.Label(
                empty_frame, text='没有发现干扰进程！',
                font=('Microsoft YaHei UI', 16, 'bold'),
                fg=COLORS['success'], bg=COLORS['bg_dark']
            ).pack(pady=(10, 5))
            
            tk.Label(
                empty_frame, text='系统当前很干净，OBS 可以正常运行',
                font=('Microsoft YaHei UI', 10),
                fg=COLORS['text_secondary'], bg=COLORS['bg_dark']
            ).pack()
        else:
            for category_name, proc_list in results.items():
                data = PROCESS_DB.get(category_name, {
                    'color': '#888',
                    'description': '',
                })
                section = CategorySection(
                    self.process_container, category_name, data, proc_list
                )
                section.pack(fill='x', pady=(0, 0))
                self.sections[category_name] = section
        
        # Update stats
        self.stats_total.configure(
            text=f'共发现 {total_procs} 个相关进程 | '
                 f'最近刷新: {datetime.now().strftime("%H:%M:%S")}'
        )
        
        # Re-apply filter
        if self.current_filter:
            self._on_search(self.current_filter)
        
        self.status_bar.set_status(f'✅ 扫描完成 - 发现 {total_procs} 个相关进程', COLORS['success'])
        self._log(f'扫描完成: 共 {len(results)} 个类别, {total_procs} 个进程')
    
    def _kill_selected(self, categories=None):
        """Kill processes by category filter"""
        def worker():
            killed = 0
            failed = 0
            target_sections = {}
            
            if categories:
                for cat in categories:
                    if cat in self.sections:
                        target_sections[cat] = self.sections[cat]
            else:
                target_sections = dict(self.sections)
            
            for cat_name, section in target_sections.items():
                self.root.after(0, lambda n=cat_name: self._log(f'正在清退: {n}...'))
                for card in section.cards[:]:
                    if card.winfo_exists():
                        success, msg = kill_process_by_pid(card.pid)
                        if success:
                            killed += 1
                            self.root.after(0, lambda c=card: c.destroy())
                        else:
                            failed += 1
            
            self.root.after(0, lambda: self._log(f'清退完成: 成功 {killed}, 失败 {failed}', 'ok' if failed == 0 else 'warn'))
            self.root.after(500, self._refresh)
        
        self._set_loading(True)
        threading.Thread(target=worker, daemon=True).start()
    
    def _kill_all_everything(self):
        if not messagebox.askyesno(
            "确认操作",
            "⚠ 这将终止所有发现的干扰进程！\n\n"
            "包括:\n"
            "  • OBS Studio 及其子进程\n"
            "  • ASUS Armoury Crate 全家桶\n"
            "  • 流媒体/录制工具\n"
            "  • 游戏覆盖/外设工具\n\n"
            "确定要继续吗？",
            parent=self.root
        ):
            return
        self._kill_selected()
    
    def _kill_asu_sonly(self):
        if not messagebox.askyesno(
            "确认操作",
            "⚠ 将清理 ASUS 相关进程\n\n"
            "适合在 OBS 安装器报 'File in use by ASUS NodeJS Web Framework' 时使用\n\n"
            "不会影响 ASUS 服务和计划任务",
            parent=self.root
        ):
            return
        self._kill_selected(categories=["ASUS 全家桶"])
    
    def _reset_config(self):
        # Check OBS running
        obs_dir = get_obs_config_dir()
        if not obs_dir.exists():
            messagebox.showinfo(
                "提示",
                "未找到 OBS 配置目录，无需重置。\n\n"
                f"检查路径: {obs_dir}\n\n"
                "OBS 可能尚未安装或从未启动。",
                parent=self.root
            )
            return
        
        if not messagebox.askyesno(
            "确认操作",
            "⚠ 将重置 OBS 为默认设置！\n\n"
            "操作会自动备份当前配置到:\n"
            f"  {Path(os.environ['APPDATA'])}/obs-studio-backup-[时间戳]\n\n"
            "下次启动 OBS 将运行首次设置向导。\n\n"
            "确定要继续吗？",
            parent=self.root
        ):
            return
        
        self._log('正在备份并重置 OBS 配置...')
        success, msg, backup_path = reset_obs_config()
        
        if success:
            self._log(f'配置已重置! 备份: {backup_path}', 'ok')
            messagebox.showinfo(
                "操作成功",
                f"OBS 配置已重置为默认值！\n\n"
                f"备份保存在: {backup_path}\n\n"
                f"下次启动 OBS 将运行首次设置向导。",
                parent=self.root
            )
        else:
            self._log(f'重置失败: {msg}', 'err')
            messagebox.showerror("操作失败", msg, parent=self.root)
    
    def _one_click(self):
        if not messagebox.askyesno(
            "确认一键操作",
            "⚠ 这将在一次操作中完成:\n\n"
            "  1. 清退所有干扰进程\n"
            "  2. 备份并重置 OBS 配置\n\n"
            "确定要继续吗？",
            parent=self.root
        ):
            return
        
        def worker():
            # Phase 1: Kill all
            self.root.after(0, lambda: self._log('===== 一键模式开始 ====='))
            self.root.after(0, lambda: self._log('第1步: 清退所有进程...'))
            self.root.after(0, lambda: self.status_bar.set_status('⚡ 一键模式 - 正在清退进程...', COLORS['warning']))
            
            killed = 0
            for section in list(self.sections.values()):
                for card in section.cards[:]:
                    if card.winfo_exists():
                        success, _ = kill_process_by_pid(card.pid)
                        if success:
                            killed += 1
            
            self.root.after(0, lambda: self._log(f'第1步完成: 终止 {killed} 个进程', 'ok'))
            
            # Phase 2: Reset config
            self.root.after(0, lambda: self.status_bar.set_status('⚡ 一键模式 - 正在重置配置...', COLORS['warning']))
            self.root.after(0, lambda: self._log('第2步: 重置 OBS 配置...'))
            
            success, msg, backup = reset_obs_config()
            
            if success:
                self.root.after(0, lambda: self._log(f'第2步完成: {msg}', 'ok'))
                self.root.after(0, lambda: self._log('===== 一键操作全部完成! =====', 'ok'))
                self.root.after(0, lambda: messagebox.showinfo(
                    "操作完成",
                    "✅ 一键操作完成！\n\n"
                    f"已终止 {killed} 个干扰进程\n"
                    f"OBS 配置已重置\n"
                    f"备份: {backup}\n\n"
                    "可以重新启动 OBS 了。",
                    parent=self.root
                ))
            else:
                self.root.after(0, lambda: self._log(f'第2步失败: {msg}', 'err'))
                self.root.after(0, lambda: messagebox.showerror(
                    "操作失败",
                    f"清退进程成功 ({killed}个)，但重置配置失败:\n{msg}",
                    parent=self.root
                ))
            
            self.root.after(500, self._refresh)
            self.root.after(0, lambda: self._set_loading(False))
        
        self._set_loading(True)
        threading.Thread(target=worker, daemon=True).start()
    
    # ─── CONFIG TOOLS DIALOG ───
    def _show_config_tools(self):
        dialog = tk.Toplevel(self.root)
        dialog.title('配置工具')
        dialog.geometry('420x390')
        dialog.configure(bg=COLORS['bg_panel'])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center on parent
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 420) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 390) // 2
        dialog.geometry(f'+{x}+{y}')
        
        # Title header (inline, not a separate packed frame)
        header = tk.Frame(dialog, bg=COLORS['bg_panel'])
        header.pack(fill='x', padx=25, pady=(20, 5))
        tk.Label(
            header, text='🔧 高级工具',
            font=('Microsoft YaHei UI', 13, 'bold'),
            fg=COLORS['accent_gold'], bg=COLORS['bg_panel']
        ).pack(anchor='w')
        tk.Frame(header, height=2, bg=COLORS['accent_gold']).pack(fill='x', pady=(5, 0))
        
        body = tk.Frame(dialog, bg=COLORS['bg_panel'])
        body.pack(fill='both', expand=True, padx=25, pady=(15, 20))
        
        # Show config path
        obs_dir = get_obs_config_dir()
        path_frame = tk.Frame(body, bg=COLORS['bg_panel'])
        path_frame.pack(fill='x', pady=5)
        
        tk.Label(
            path_frame, text='OBS 配置路径:',
            font=('Microsoft YaHei UI', 10),
            fg=COLORS['text_secondary'], bg=COLORS['bg_panel']
        ).pack(anchor='w')
        
        tk.Label(
            path_frame, text=str(obs_dir),
            font=('Consolas', 9),
            fg=COLORS['text_primary'], bg=COLORS['bg_panel']
        ).pack(anchor='w', pady=(2, 0))
        
        if obs_dir.exists():
            tk.Label(
                path_frame, text='✅ 配置目录存在',
                font=('Microsoft YaHei UI', 9),
                fg=COLORS['success'], bg=COLORS['bg_panel']
            ).pack(anchor='w')
        else:
            tk.Label(
                path_frame, text='❌ 配置目录不存在',
                font=('Microsoft YaHei UI', 9),
                fg=COLORS['danger'], bg=COLORS['bg_panel']
            ).pack(anchor='w')
        
        # Separator
        tk.Frame(body, height=1, bg=COLORS['border']).pack(fill='x', pady=12)
        
        # Buttons
        btn_frame = tk.Frame(body, bg=COLORS['bg_panel'])
        btn_frame.pack(fill='x')
        
        ModernButton(
            btn_frame, '📂 打开配置目录',
            command=lambda: os.startfile(str(obs_dir)) if obs_dir.exists() else None,
            variant='ghost'
        ).pack(fill='x', pady=3)
        
        ModernButton(
            btn_frame, '📋 复制配置路径',
            command=lambda: self.root.clipboard_append(str(obs_dir)),
            variant='ghost'
        ).pack(fill='x', pady=3)
        
        ModernButton(
            btn_frame, '🗑 清除配置（仅限手动）',
            command=lambda: self._manual_clean(obs_dir),
            variant='danger'
        ).pack(fill='x', pady=3)
    
    def _manual_clean(self, obs_dir):
        if not obs_dir.exists():
            messagebox.showinfo("提示", "配置目录不存在", parent=self.root)
            return
        
        if messagebox.askyesno(
            "⚠ 最终确认",
            f"将直接删除:\n{obs_dir}\n\n此操作不可逆！确定？",
            parent=self.root
        ):
            try:
                import shutil
                shutil.rmtree(obs_dir)
                messagebox.showinfo("完成", "配置已删除", parent=self.root)
            except Exception as e:
                messagebox.showerror("失败", str(e), parent=self.root)
    
    # ─── FIX ALL ISSUES ───
    def _fix_all_issues(self):
        """Comprehensive OBS issue fixer"""
        if not messagebox.askyesno(
            "🩺 一键修复 OBS 问题",
            "此功能将执行以下操作:\n\n"
            "  1. 终止所有 OBS 相关进程\n"
            "  2. 清理 Shader 缓存和崩溃日志\n"
            "  3. 检查已知冲突插件\n"
            "  4. 备份并重置 OBS 配置（会询问）\n\n"
            "这些操作通常能解决:\n"
            "  • OBS 崩溃/闪退\n"
            "  • 黑屏/无画面\n"
            "  • 插件冲突\n"
            "  • 配置损坏\n\n"
            "确定要开始修复吗？",
            parent=self.root
        ):
            return
        
        # Open a progress dialog
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title('🩺 OBS 问题修复')
        progress_dialog.geometry('580x540')
        progress_dialog.configure(bg=COLORS['bg_panel'])
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()
        
        # Center on parent
        progress_dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 580) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 540) // 2
        progress_dialog.geometry(f'+{x}+{y}')
        
        # ─── Pre-create bottom summary area (reserved space, shown when done) ───
        btn_frame = tk.Frame(progress_dialog, bg=COLORS['bg_panel'])
        btn_frame.pack(side='bottom', fill='x', padx=25, pady=(10, 20))
        
        # Summary label placeholder
        summary_label = tk.Label(
            btn_frame, text='',
            font=('Microsoft YaHei UI', 10, 'bold'),
            fg=COLORS['success'], bg=COLORS['bg_panel'],
            wraplength=500, justify='left'
        )
        summary_label.pack(anchor='w', pady=(0, 10))
        
        # Button row placeholder
        button_row = tk.Frame(btn_frame, bg=COLORS['bg_panel'])
        button_row.pack(fill='x')
        
        # ─── Header ───
        header = tk.Frame(progress_dialog, bg=COLORS['bg_panel'])
        header.pack(fill='x', padx=25, pady=(20, 5))
        tk.Label(
            header, text='🩺 OBS 问题诊断与修复',
            font=('Microsoft YaHei UI', 14, 'bold'),
            fg=COLORS['accent_gold'], bg=COLORS['bg_panel']
        ).pack(anchor='w')
        
        # ─── Progress log ───
        log_frame = tk.Frame(progress_dialog, bg=COLORS['bg_dark'])
        log_frame.pack(fill='both', expand=True, padx=25, pady=(5, 5))
        
        log_text = scrolledtext.ScrolledText(
            log_frame,
            font=('Consolas', 10),
            bg=COLORS['bg_dark'],
            fg=COLORS['text_primary'],
            insertbackground=COLORS['accent_gold'],
            relief='flat', bd=0,
            wrap='word'
        )
        log_text.pack(fill='both', expand=True)
        log_text.configure(state='disabled')
        
        def append_log(msg, tag=None):
            log_text.configure(state='normal')
            ts = datetime.now().strftime('%H:%M:%S')
            emoji_map = {'ok': '✅', 'err': '❌', 'warn': '⚠️', 'info': 'ℹ️'}
            emoji = emoji_map.get(tag, '  ')
            
            color_map = {'ok': '#00b894', 'err': '#e94560', 'warn': '#fdcb6e', 'info': '#74b9ff'}
            color = color_map.get(tag, COLORS['text_primary'])
            
            log_text.tag_config(color or 'default', foreground=color)
            log_text.insert('end', f'[{ts}] {emoji} ', color or 'default')
            log_text.insert('end', f'{msg}\n')
            log_text.see('end')
            log_text.configure(state='disabled')
            progress_dialog.update()
        
        # Run fix in background
        def worker():
            append_log('开始 OBS 综合诊断修复...', 'info')
            
            results = fix_obs_issues(
                log_callback=append_log,
                ask_config_reset=True,
                parent=progress_dialog
            )
            
            # Show summary (populate pre-created button area)
            self.root.after(0, lambda: _show_summary(results))
        
        def _show_summary(results):
            """Populate the pre-created button area with results"""
            errors = len(results['errors'])
            if errors == 0:
                summary = '🟢 修复完成，未发现错误！可以重新启动 OBS 了。'
                summary_color = COLORS['success']
            else:
                summary = f'🟡 修复完成，但遇到 {errors} 个错误。'
                summary_color = COLORS['warning']
            
            summary_label.configure(text=summary, fg=summary_color)
            
            # Clear existing buttons
            for w in button_row.winfo_children():
                w.destroy()
            
            if results.get('config_backup'):
                ModernButton(
                    button_row, '📂 打开备份目录',
                    command=lambda p=results['config_backup']: os.startfile(str(Path(p).parent)),
                    variant='ghost'
                ).pack(side='left', padx=(0, 5))
            
            ModernButton(
                button_row, '📦 管理插件',
                command=lambda: [progress_dialog.destroy(), self._show_plugin_manager()],
                variant='info'
            ).pack(side='left', padx=5)
            
            ModernButton(
                button_row, '✅ 完成',
                command=progress_dialog.destroy,
                variant='primary'
            ).pack(side='right')
            
            self.root.after(0, self._refresh)
        
        threading.Thread(target=worker, daemon=True).start()
    
    # ─── PLUGIN MANAGER ───
    def _show_plugin_manager(self):
        """Plugin management dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title('📦 OBS 插件管理')
        dialog.geometry('750x620')
        dialog.configure(bg=COLORS['bg_panel'])
        dialog.resizable(True, True)
        dialog.minsize(600, 500)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center
        dialog.update_idletasks()
        x = self.root.winfo_x() + max(0, (self.root.winfo_width() - 750) // 2)
        y = self.root.winfo_y() + max(0, (self.root.winfo_height() - 620) // 2)
        dialog.geometry(f'+{x}+{y}')
        
        # Header
        header = tk.Frame(dialog, bg=COLORS['bg_panel'])
        header.pack(fill='x', padx=25, pady=(20, 5))
        tk.Label(
            header, text='📦 OBS 插件管理',
            font=('Microsoft YaHei UI', 16, 'bold'),
            fg=COLORS['accent_gold'], bg=COLORS['bg_panel']
        ).pack(side='left')
        
        # Scan state - will be updated
        plugin_state = {
            'plugins': [], 'checkboxes': {}, 'select_all_var': tk.BooleanVar(value=False),
            'sort_key': 'default',  # 'default', 'install_time', 'builtin'
            'sort_reverse': False,
        }
        
        # ─── Toolbar Row 1: scan + sort ───
        toolbar1 = tk.Frame(dialog, bg=COLORS['bg_panel'])
        toolbar1.pack(fill='x', padx=25, pady=(10, 2))
        
        ModernButton(
            toolbar1, '🔄 重新扫描',
            command=lambda: _rescan(),
            variant='ghost'
        ).pack(side='left', padx=(0, 5))
        
        # Sort buttons
        sort_time_btn = ModernButton(
            toolbar1, '🕐 按安装时间',
            command=lambda: _toggle_sort('install_time'),
            variant='ghost'
        )
        sort_time_btn.pack(side='left', padx=(0, 3))
        
        sort_builtin_btn = ModernButton(
            toolbar1, '🏷 OBS自带/第三方',
            command=lambda: _toggle_sort('builtin'),
            variant='ghost'
        )
        sort_builtin_btn.pack(side='left', padx=(0, 3))
        plugin_state['sort_btns'] = {'install_time': sort_time_btn, 'builtin': sort_builtin_btn}
        
        # ─── Toolbar Row 2: manage + actions ───
        toolbar2 = tk.Frame(dialog, bg=COLORS['bg_panel'])
        toolbar2.pack(fill='x', padx=25, pady=(2, 5))
        
        # Select all checkbox
        select_all_cb = tk.Checkbutton(
            toolbar2, text='全选/取消全选',
            variable=plugin_state['select_all_var'],
            command=lambda: _toggle_all(plugin_state['select_all_var'].get()),
            font=('Microsoft YaHei UI', 10),
            fg=COLORS['text_primary'], bg=COLORS['bg_panel'],
            selectcolor=COLORS['bg_card'],
            activebackground=COLORS['bg_panel'],
            activeforeground=COLORS['text_primary']
        )
        select_all_cb.pack(side='left')
        
        # Spacer
        tk.Frame(toolbar2, bg=COLORS['bg_panel']).pack(side='left', fill='x', expand=True)
        
        # Action buttons
        ModernButton(
            toolbar2, '🗑 删除选中',
            command=lambda: _delete_selected(),
            variant='danger'
        ).pack(side='right', padx=(5, 0))
        
        ModernButton(
            toolbar2, '💣 删除全部',
            command=lambda: _delete_all(),
            variant='danger'
        ).pack(side='right', padx=5)
        
        # ─── Stats Bar (full-width separate row, below toolbars) ───
        stats_bar = tk.Frame(dialog, bg=COLORS['bg_panel'])
        stats_bar.pack(fill='x', padx=25, pady=(0, 5))
        
        stats_label = tk.Label(
            stats_bar, text='',
            font=('Microsoft YaHei UI', 9),
            fg=COLORS['text_muted'], bg=COLORS['bg_panel'],
            anchor='w', justify='left'
        )
        stats_label.pack(fill='x')
        plugin_state['stats_label'] = stats_label
        
        # Plugin list container (scrollable)
        list_frame = tk.Frame(dialog, bg=COLORS['bg_dark'])
        list_frame.pack(fill='both', expand=True, padx=25, pady=(5, 15))
        
        canvas = tk.Canvas(list_frame, bg=COLORS['bg_dark'], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=canvas.yview)
        plugin_container = tk.Frame(canvas, bg=COLORS['bg_dark'])
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        
        canvas_window = canvas.create_window((0, 0), window=plugin_container, anchor='nw')
        
        def _on_plugin_canvas_configure(e):
            canvas.itemconfig(canvas_window, width=e.width)
        
        def _on_plugin_container_configure(e):
            canvas.configure(scrollregion=canvas.bbox('all'))
        
        plugin_container.bind('<Configure>', _on_plugin_container_configure)
        canvas.bind('<Configure>', _on_plugin_canvas_configure)
        
        # Mousewheel
        def _bind_mw(e):
            canvas.bind_all('<MouseWheel>', lambda ev: canvas.yview_scroll(int(-1*(ev.delta/120)), 'units'))
        def _unbind_mw(e):
            canvas.unbind_all('<MouseWheel>')
        canvas.bind('<Enter>', _bind_mw)
        canvas.bind('<Leave>', _unbind_mw)
        
        plugin_state['canvas'] = canvas
        plugin_state['container'] = plugin_container
        plugin_state['dialog'] = dialog
        
        # Sort toggle
        def _toggle_sort(key):
            if plugin_state['sort_key'] == key:
                plugin_state['sort_reverse'] = not plugin_state['sort_reverse']
            else:
                plugin_state['sort_key'] = key
                plugin_state['sort_reverse'] = False
            
            # Update button visual state
            for k, btn in plugin_state['sort_btns'].items():
                if k == plugin_state['sort_key']:
                    arrow = ' 🔽' if not plugin_state['sort_reverse'] else ' 🔼'
                    btn.configure(
                        bg=COLORS['accent_gold'], fg=COLORS['bg_dark'],
                        text=btn.cget('text').rstrip(' 🔼🔽') + arrow
                    )
                    btn._normal_color = COLORS['accent_gold']
                else:
                    btn.configure(
                        bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                        text=btn.cget('text').rstrip(' 🔼🔽')
                    )
                    btn._normal_color = COLORS['bg_panel']
            
            _build_plugin_rows(plugin_state['plugins'])
        
        # Build plugin row helper
        def _build_plugin_rows(plugins):
            """Build plugin list UI rows, applying current sort"""
            # Apply sort
            sort_key = plugin_state['sort_key']
            if sort_key == 'install_time':
                plugins = sorted(
                    plugins,
                    key=lambda p: p.install_time or datetime(2000, 1, 1),
                    reverse=plugin_state['sort_reverse']
                )
            elif sort_key == 'builtin':
                plugins = sorted(
                    plugins,
                    key=lambda p: (not p.is_builtin, p.name.lower()),
                    reverse=plugin_state['sort_reverse']
                )
            
            plugin_state['plugins'] = plugins
            plugin_state['checkboxes'] = {}
            
            # Clear
            for w in plugin_container.winfo_children():
                w.destroy()
            
            if not plugins:
                empty = tk.Frame(plugin_container, bg=COLORS['bg_dark'])
                empty.pack(fill='x', pady=40)
                tk.Label(
                    empty, text='📦',
                    font=('Segoe UI Emoji', 36),
                    fg=COLORS['text_muted'], bg=COLORS['bg_dark']
                ).pack()
                tk.Label(
                    empty, text='未检测到 OBS 插件\n请确保 OBS 已安装',
                    font=('Microsoft YaHei UI', 12),
                    fg=COLORS['text_muted'], bg=COLORS['bg_dark'],
                    justify='center'
                ).pack(pady=(10, 0))
                _update_stats()
                return
            
            for idx, plugin in enumerate(plugins):
                var = tk.BooleanVar(value=False)
                plugin_state['checkboxes'][idx] = var
                
                row = tk.Frame(plugin_container, bg=COLORS['bg_card'] if idx % 2 == 0 else COLORS['bg_panel'])
                row.pack(fill='x', pady=1)
                
                # Checkbox
                cb = tk.Checkbutton(
                    row, variable=var,
                    command=lambda: _update_stats(),
                    bg=COLORS['bg_card'] if idx % 2 == 0 else COLORS['bg_panel'],
                    selectcolor=COLORS['bg_input'],
                    activebackground=COLORS['bg_card'] if idx % 2 == 0 else COLORS['bg_panel'],
                )
                cb.pack(side='left', padx=(8, 5), pady=8)
                
                # Plugin info
                info_frame = tk.Frame(row, bg=COLORS['bg_card'] if idx % 2 == 0 else COLORS['bg_panel'])
                info_frame.pack(side='left', fill='x', expand=True, pady=6)
                
                tk.Label(
                    info_frame, text=plugin.name,
                    font=('Consolas', 10, 'bold'),
                    fg=COLORS['accent_gold'],
                    bg=COLORS['bg_card'] if idx % 2 == 0 else COLORS['bg_panel'],
                    anchor='w'
                ).pack(anchor='w')
                
                meta_frame = tk.Frame(info_frame, bg=COLORS['bg_card'] if idx % 2 == 0 else COLORS['bg_panel'])
                meta_frame.pack(anchor='w', pady=(2, 0))
                
                # Built-in / third-party badge
                if plugin.is_builtin:
                    badge_text = '🏛 OBS内置'
                    badge_fg = COLORS['info']
                else:
                    badge_text = '🧩 第三方'
                    badge_fg = COLORS['accent_orange']
                
                tk.Label(
                    meta_frame, text=f'{badge_text}  •  {plugin.size_str}  •  {plugin.location_label}',
                    font=('Microsoft YaHei UI', 8),
                    fg=COLORS['text_muted'],
                    bg=COLORS['bg_card'] if idx % 2 == 0 else COLORS['bg_panel']
                ).pack(side='left')
                
                tk.Label(
                    meta_frame, text=f'  {plugin.filename}',
                    font=('Consolas', 8),
                    fg=COLORS['text_muted'],
                    bg=COLORS['bg_card'] if idx % 2 == 0 else COLORS['bg_panel']
                ).pack(side='left')
                
                # Extra files indicator
                if plugin.extra_count > 0:
                    tk.Label(
                        info_frame,
                        text=f'📎 关联文件 {plugin.extra_count} 项 ({plugin.extra_size_str})',
                        font=('Microsoft YaHei UI', 8),
                        fg=COLORS['info'],
                        bg=COLORS['bg_card'] if idx % 2 == 0 else COLORS['bg_panel'],
                        anchor='w'
                    ).pack(anchor='w')

                # Install time
                tk.Label(
                    info_frame, text=f'🕐 安装时间: {plugin.install_time_str}',
                    font=('Microsoft YaHei UI', 8),
                    fg=COLORS['text_muted'],
                    bg=COLORS['bg_card'] if idx % 2 == 0 else COLORS['bg_panel'],
                    anchor='w'
                ).pack(anchor='w')

                # Path (truncated)
                path_str = str(plugin.path.parent)
                if len(path_str) > 60:
                    path_str = '...' + path_str[-57:]
                tk.Label(
                    info_frame, text=path_str,
                    font=('Consolas', 7),
                    fg=COLORS['text_muted'],
                    bg=COLORS['bg_card'] if idx % 2 == 0 else COLORS['bg_panel'],
                    anchor='w'
                ).pack(anchor='w')
                
                # Delete single
                del_btn = tk.Label(
                    row, text='🗑',
                    font=('Segoe UI Emoji', 14),
                    fg=COLORS['danger'],
                    bg=COLORS['bg_card'] if idx % 2 == 0 else COLORS['bg_panel'],
                    cursor='hand2'
                )
                del_btn.pack(side='right', padx=10)
                del_btn.bind('<Button-1>', lambda e, p=plugin: _confirm_delete_single(p))
            
            _update_stats()
        
        def _update_stats():
            total = len(plugin_state['plugins'])
            checked = sum(1 for v in plugin_state['checkboxes'].values() if v.get())
            total_size = sum(p.size for p in plugin_state['plugins'])
            total_extra_size = sum(getattr(p, 'extra_size', 0) for p in plugin_state['plugins'])
            size_str = PluginInfo._fmt_size(total_size)
            extra_size_str = PluginInfo._fmt_size(total_extra_size)
            builtin_count = sum(1 for p in plugin_state['plugins'] if p.is_builtin)
            extra_count = sum(getattr(p, 'extra_count', 0) for p in plugin_state['plugins'])

            sort_hint = ''
            sk = plugin_state['sort_key']
            if sk == 'install_time':
                sort_hint = ' | 按安装时间'
            elif sk == 'builtin':
                sort_hint = ' | 按OBS内置/第三方'

            plugin_state['stats_label'].configure(
                text=f'共 {total} 插件 ({builtin_count}内置, {total - builtin_count}第三方), '
                     f'{checked} 选中  |  插件 {size_str} + 关联文件 {extra_size_str}{sort_hint}'
            )
        
        def _toggle_all(state):
            for var in plugin_state['checkboxes'].values():
                var.set(state)
            _update_stats()
        
        def _rescan():
            plugin_state['stats_label'].configure(text='正在扫描...')
            dialog.update()
            
            def do_scan():
                plugins = scan_obs_plugins()
                self.root.after(0, lambda: _build_plugin_rows(plugins))
            threading.Thread(target=do_scan, daemon=True).start()
        
        def _confirm_delete_single(plugin):
            # Build deletion preview
            extra_lines = []
            for f in plugin.extra_files:
                if f.is_dir():
                    extra_lines.append(f'  [目录] {f.name}')
                else:
                    extra_lines.append(f'  [文件] {f.name}')
            extra_text = '\n'.join(extra_lines) if extra_lines else '  (无)'

            if not messagebox.askyesno(
                "确认删除",
                f"确定要删除插件「{plugin.name}」吗？\n\n"
                f"主文件: {plugin.filename} ({plugin.size_str})\n"
                f"位置: {plugin.location_label}\n\n"
                f"以下关联文件将一并删除:\n{extra_text}\n\n"
                "⚠ 删除后无法恢复！",
                parent=dialog
            ):
                return

            results = plugin.delete()
            for status, msg in results:
                tag = 'ok' if status == 'ok' else ('warn' if status == 'warn' else 'err')
                self._log(f'[插件管理] {msg}', tag)
            
            messagebox.showinfo("完成", f"插件「{plugin.name}」已删除", parent=dialog)
            _rescan()
        
        def _delete_selected():
            selected = []
            for idx, var in plugin_state['checkboxes'].items():
                if var.get():
                    selected.append(plugin_state['plugins'][idx])

            if not selected:
                messagebox.showinfo("提示", "请先选择要删除的插件", parent=dialog)
                return

            # Build detailed deletion preview with extra files
            lines = []
            for p in selected:
                lines.append(f'  • {p.name} ({p.size_str})')
                for f in p.extra_files:
                    tag = '[目录]' if f.is_dir() else '[文件]'
                    lines.append(f'      {tag} {f.name}')
            names = '\n'.join(lines)

            total_extra = sum(p.extra_count for p in selected)
            extra_hint = f' (含 {total_extra} 项关联文件)' if total_extra > 0 else ''

            if not messagebox.askyesno(
                "确认批量删除",
                f"将删除以下 {len(selected)}  个插件{extra_hint}:\n\n{names}\n\n"
                "⚠ 此操作不可逆！关联文件 (.pdb / data目录) 也将一并删除。",
                parent=dialog
            ):
                return

            success, fail, msgs = delete_plugins(selected)
            for msg in msgs:
                self._log(f'[插件管理] {msg}')
            
            messagebox.showinfo(
                "完成",
                f"删除完成: 成功 {success}, 失败 {fail}",
                parent=dialog
            )
            _rescan()
        
        def _delete_all():
            plugins = plugin_state['plugins']
            if not plugins:
                return

            total_extra = sum(p.extra_count for p in plugins)
            names = '\n'.join(f'  • {p.name} ({p.size_str})' for p in plugins[:15])
            if len(plugins) > 15:
                names += f'\n  ... 还有 {len(plugins) - 15} 个'

            extra_hint = f' (含 {total_extra} 项关联文件)' if total_extra > 0 else ''

            if not messagebox.askyesno(
                "⚠ 确认删除全部插件",
                f"将删除全部 {len(plugins)}  个插件{extra_hint}:\n\n{names}\n\n"
                "注意:\n"
                "• 关联文件 (.pdb / data目录) 也将一并删除\n"
                "• 删除后OBS将无任何第三方插件\n"
                "• 系统自带插件（obs-filters等）也会被删除\n"
                "• 这是一项激进操作，建议先备份\n\n"
                "确定要删除全部吗？",
                parent=dialog
            ):
                return
            
            # Double confirm
            if not messagebox.askyesno(
                "⚠ 二次确认",
                "删除全部插件后，OBS 将恢复为纯原生状态。\n\n"
                "如有需要，可以重新安装插件。\n\n"
                "最后确认：删除全部插件？",
                parent=dialog
            ):
                return
            
            success, fail, msgs = delete_plugins(plugins)
            for msg in msgs:
                self._log(f'[插件管理] {msg}')
            
            messagebox.showinfo(
                "完成",
                f"全部删除完成: 成功 {success}, 失败 {fail}",
                parent=dialog
            )
            _rescan()
        
        # Initial scan
        _rescan()
    
    def run(self):
        self.root.mainloop()


# ═══════════════════════════════════════════════════════════
# TOOLTIP HELPER
# ═══════════════════════════════════════════════════════════

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind('<Enter>', self._show)
        widget.bind('<Leave>', self._hide)
    
    def _show(self, e=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 10
        y = self.widget.winfo_rooty() + 10
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f'+{x}+{y}')
        tk.Label(
            tw, text=self.text,
            font=('Microsoft YaHei UI', 9),
            bg='#2d2d2d', fg='#eaeaea',
            padx=8, pady=4, relief='flat', bd=1
        ).pack()
    
    def _hide(self, e=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


# ═══════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════

def main():
    # Check admin
    if not is_admin():
        if messagebox.askyesno(
            "需要管理员权限",
            "本工具需要管理员权限才能管理进程和配置。\n\n是否以管理员身份重新启动？"
        ):
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                f'"{__file__}"' if not getattr(sys, 'frozen', False) else f'"{sys.executable}"',
                None, 1
            )
            sys.exit(0)
        else:
            messagebox.showwarning(
                "权限不足",
                "部分功能可能无法正常工作。"
            )
    
    app = OBSManagerApp()
    app.run()


if __name__ == '__main__':
    main()
