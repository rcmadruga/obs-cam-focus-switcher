import win32gui
import win32process
import psutil
import asyncio
import simpleobsws
import time
import re
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

@dataclass
class SceneRule:
    monitor: int
    url_pattern: str
    scene_name: str

class OBSWindowSwitcher:
    def __init__(self, obs_ws_url: str = "ws://localhost:4455", obs_ws_password: str = "YOURPASSWORD"):
        """
        Initialize the OBS Window Switcher.
        
        Args:
            obs_ws_url: WebSocket URL for OBS connection
            obs_ws_password: Password for OBS WebSocket server
        """
        self.obs_ws_url = obs_ws_url
        self.obs_ws_password = obs_ws_password
        self.ws = None
        self.scene_rules: List[SceneRule] = []
        
    async def connect_obs(self):
        """Establish connection to OBS WebSocket server."""
        self.ws = simpleobsws.WebSocketClient(
            url=self.obs_ws_url,
            password=self.obs_ws_password
        )
        await self.ws.connect()
        await self.ws.wait_until_identified()
        
    def add_scene_rule(self, monitor: int, url_pattern: str, scene_name: str):
        """
        Add a rule for scene switching.
        
        Args:
            monitor: Monitor number (0-based)
            url_pattern: Regex pattern to match URL/title
            scene_name: Name of the OBS scene to switch to
        """
        rule = SceneRule(monitor, url_pattern, scene_name)
        self.scene_rules.append(rule)

    def get_chrome_windows_info(self) -> List[Tuple[int, str]]:
        """
        Get information about all visible Chrome windows.
        
        Returns:
            List of tuples containing (monitor_number, window_title)
        """
        windows_info = []
        
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    process = psutil.Process(pid)
                    if 'chrome.exe' in process.name().lower():
                        title = win32gui.GetWindowText(hwnd)
                        if title and not title.startswith('Google Chrome'):  # Skip Chrome's main window
                            rect = win32gui.GetWindowRect(hwnd)
                            center_x = (rect[0] + rect[2]) // 2
                            center_y = (rect[1] + rect[3]) // 2
                            monitor = get_monitor_at_point(center_x, center_y)
                            windows_info.append((monitor, title))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return True

        win32gui.EnumWindows(callback, None)
        return windows_info

    def find_matching_scene(self, monitor: int, window_title: str) -> Optional[str]:
        """
        Find the appropriate scene based on monitor and window title/URL.
        
        Args:
            monitor: Monitor number
            window_title: Window title (includes URL for Chrome tabs)
            
        Returns:
            Scene name or None if no rule matches
        """
        for rule in self.scene_rules:
            if (rule.monitor == monitor and 
                re.search(rule.url_pattern, window_title, re.IGNORECASE)):
                return rule.scene_name
        return None

    async def switch_scene(self, scene_name: str):
        """
        Switch OBS scene.
        
        Args:
            scene_name: Name of the scene to switch to
        """
        request = simpleobsws.Request('SetCurrentProgramScene', {
            'sceneName': scene_name
        })
        await self.ws.call(request)

    async def monitor_chrome_windows(self, check_interval: float = 1.0):
        """
        Main loop to monitor Chrome windows and switch scenes.
        
        Args:
            check_interval: How often to check window positions (in seconds)
        """
        last_scene = None
        
        while True:
            print("Checking Chrome windows...")
            windows = self.get_chrome_windows_info()
            print(windows)
            
            for monitor, title in windows:
                scene_name = self.find_matching_scene(monitor, title)
                if scene_name and scene_name != last_scene:
                    await self.switch_scene(scene_name)
                    last_scene = scene_name
                    print(f"Switching to scene '{scene_name}' for window '{title}' on monitor {monitor}")
                    break
                    
            await asyncio.sleep(check_interval)

def get_monitor_at_point(x: int, y: int) -> int:
    """
    Get monitor number at given coordinates.
    
    Args:
        x: X coordinate
        y: Y coordinate
        
    Returns:
        Monitor number (0-based)
    """
    import win32api
    
    monitors = win32api.EnumDisplayMonitors()
    for i, (handle, device, rect) in enumerate(monitors):
        if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
            return i
    return 0

async def main():
    # Initialize the window switcher
    switcher = OBSWindowSwitcher(
        obs_ws_url="ws://10.0.0.9:4455",
        obs_ws_password="02C8Sp1p6r2D4CWU"
    )
    
    # Connect to OBS
    await switcher.connect_obs()
    
    # Set up rules for scene switching
    # Examples:
    switcher.add_scene_rule(
        monitor=0,  # Primary monitor
        url_pattern=r"Fleet Management",  # Match any YouTube URL
        scene_name="Logi-Only"
    )

    # switcher.add_scene_rule(
    #     monitor=0,  # Primary monitor
    #     url_pattern=r"youtube\.com",  # Match any YouTube URL
    #     scene_name="YouTube Scene"
    # )
    
    # switcher.add_scene_rule(
    #     monitor=1,  # Secondary monitor
    #     url_pattern=r"twitch\.tv",  # Match any Twitch URL
    #     scene_name="Twitch Scene"
    # )
    
    switcher.add_scene_rule(
        monitor=0,  # Third monitor
        url_pattern=r".*",  # Match any URL (default scene for this monitor)
        scene_name="Default Scene"
    )
    
    # Start monitoring
    await switcher.monitor_chrome_windows()

if __name__ == "__main__":
    asyncio.run(main())