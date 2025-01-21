import win32gui
import win32process
import psutil
import asyncio
import simpleobsws
import time
import re
from typing import Dict, Optional, List, Tuple, NamedTuple
from dataclasses import dataclass

@dataclass
class SceneRule:
    monitor: int
    url_pattern: str
    scene_name: str

class WindowState(NamedTuple):
    monitor: int
    title: str
    scene: str

class OBSWindowSwitcher:
    def __init__(self, obs_ws_url: str = "ws://localhost:4455", obs_ws_password: str = "your_password_here"):
        self.obs_ws_url = obs_ws_url
        self.obs_ws_password = obs_ws_password
        self.ws = None
        self.scene_rules: List[SceneRule] = []
        
        # Cache states
        self.current_scene: Optional[str] = None
        self.last_window_state: Optional[WindowState] = None
        self.cached_window_states: Dict[int, WindowState] = {}  # monitor -> WindowState
        
    async def connect_obs(self):
        """Establish connection to OBS WebSocket server."""
        self.ws = simpleobsws.WebSocketClient(
            url=self.obs_ws_url,
            password=self.obs_ws_password
        )
        await self.ws.connect()
        await self.ws.wait_until_identified()
        
        # Get initial scene
        request = simpleobsws.Request('GetCurrentProgramScene')
        response = await self.ws.call(request)
        if response.ok():
            self.current_scene = response.responseData.get('currentProgramSceneName')
        
    def add_scene_rule(self, monitor: int, url_pattern: str, scene_name: str):
        """Add a rule for scene switching."""
        rule = SceneRule(monitor, url_pattern, scene_name)
        self.scene_rules.append(rule)

    def get_chrome_windows_info(self) -> List[Tuple[int, str]]:
        """Get information about all visible Chrome windows."""
        windows_info = []
        
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    process = psutil.Process(pid)
                    if 'chrome.exe' in process.name().lower():
                        title = win32gui.GetWindowText(hwnd)
                        if title and not title.startswith('Google Chrome'):
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
        """Find the appropriate scene based on monitor and window title/URL."""
        for rule in self.scene_rules:
            if (rule.monitor == monitor and 
                re.search(rule.url_pattern, window_title, re.IGNORECASE)):
                return rule.scene_name
        return None

    def has_state_changed(self, new_state: WindowState) -> bool:
        """Check if the window state has meaningfully changed."""
        if new_state.monitor not in self.cached_window_states:
            return True
            
        cached_state = self.cached_window_states[new_state.monitor]
        # Only consider it changed if either:
        # 1. The scene has changed
        # 2. The monitor has changed
        # 3. The URL pattern matches differently
        return (cached_state.scene != new_state.scene or
                cached_state.monitor != new_state.monitor)

    async def switch_scene(self, scene_name: str):
        """Switch OBS scene if it's different from current scene."""
        if scene_name != self.current_scene:
            request = simpleobsws.Request('SetCurrentProgramScene', {
                'sceneName': scene_name
            })
            response = await self.ws.call(request)
            if response.ok():
                self.current_scene = scene_name
                return True
        return False

    async def monitor_chrome_windows(self, check_interval: float = 1.0):
        """Main loop to monitor Chrome windows and switch scenes."""
        while True:
            windows = self.get_chrome_windows_info()
            state_changed = False
            
            for monitor, title in windows:
                scene_name = self.find_matching_scene(monitor, title)
                if scene_name:
                    new_state = WindowState(monitor, title, scene_name)
                    
                    if self.has_state_changed(new_state):
                        state_changed = True
                        self.cached_window_states[monitor] = new_state
                        
                        if await self.switch_scene(scene_name):
                            print(f"Scene switched to '{scene_name}' for window '{title}' on monitor {monitor}")
                    break
                    
            if not state_changed:
                # If no state change was detected, we can sleep a bit longer
                await asyncio.sleep(check_interval * 2)
            else:
                # If there was a change, keep the normal interval to catch quick transitions
                await asyncio.sleep(check_interval)

def get_monitor_at_point(x: int, y: int) -> int:
    """Get monitor number at given coordinates."""
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
        obs_ws_password="your_password_here"
    )
    
    # Connect to OBS
    await switcher.connect_obs()
    
    # Example rules
    switcher.add_scene_rule(
        monitor=1,  # Primary monitor
        url_pattern=r"Fleet Management",  # Match any YouTube URL
        scene_name="Logi-Only"
    )

    switcher.add_scene_rule(
        monitor=0,  # Primary monitor
        url_pattern=r"Fleet Management",  # Match any YouTube URL
        scene_name="BRIO-Only"
    )

    switcher.add_scene_rule(
        monitor=0,
        url_pattern=r"youtube\.com",
        scene_name="YouTube Scene"
    )
    
    switcher.add_scene_rule(
        monitor=1,
        url_pattern=r"twitch\.tv",
        scene_name="Twitch Scene"
    )
    
    # Start monitoring
    await switcher.monitor_chrome_windows()

if __name__ == "__main__":
    asyncio.run(main())