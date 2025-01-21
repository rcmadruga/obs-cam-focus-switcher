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
    hash: str  # Added to track unique states

class OBSWindowSwitcher:
    def __init__(self, obs_ws_url: str = "ws://localhost:4455", obs_ws_password: str = "your_password_here"):
        self.obs_ws_url = obs_ws_url
        self.obs_ws_password = obs_ws_password
        self.ws = None
        self.scene_rules: List[SceneRule] = []
        self.current_scene: Optional[str] = None
        self.last_state_hash: Optional[str] = None
        
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
            print(f"Initial scene: {self.current_scene}")
        
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
                            print(f"Found window: Monitor {monitor}, Title: {title}")  # Debug print
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

    def create_state_hash(self, monitor: int, title: str, scene: str) -> str:
        """Create a unique hash for the current state."""
        return f"{monitor}:{title}:{scene}"

    async def switch_scene(self, scene_name: str):
        """Switch OBS scene if it's different from current scene."""
        if scene_name != self.current_scene:
            print(f"Attempting to switch from {self.current_scene} to {scene_name}")  # Debug print
            request = simpleobsws.Request('SetCurrentProgramScene', {
                'sceneName': scene_name
            })
            response = await self.ws.call(request)
            if response.ok():
                self.current_scene = scene_name
                print(f"Successfully switched to {scene_name}")  # Debug print
                return True
            else:
                print(f"Failed to switch scene: {response}")  # Debug print
        return False

    async def monitor_chrome_windows(self, check_interval: float = 1.0):
        """Main loop to monitor Chrome windows and switch scenes."""
        print("Starting monitoring loop...")  # Debug print
        
        while True:
            windows = self.get_chrome_windows_info()
            
            for monitor, title in windows:
                scene_name = self.find_matching_scene(monitor, title)
                if scene_name:
                    current_hash = self.create_state_hash(monitor, title, scene_name)
                    
                    # Always print current state for debugging
                    print(f"\nCurrent state:")
                    print(f"Monitor: {monitor}")
                    print(f"Title: {title}")
                    print(f"Scene: {scene_name}")
                    print(f"Current hash: {current_hash}")
                    print(f"Last hash: {self.last_state_hash}")
                    
                    # Check if state has changed
                    if current_hash != self.last_state_hash:
                        print("State change detected!")  # Debug print
                        if await self.switch_scene(scene_name):
                            self.last_state_hash = current_hash
                            print(f"Updated state hash to: {self.last_state_hash}")  # Debug print
                    break
            
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
        obs_ws_url="ws://localhost:4455",
        obs_ws_password="your_password_here"
    )
    
    # Connect to OBS
    await switcher.connect_obs()
    
    # Example rules
    switcher.add_scene_rule(
        monitor=1,
        url_pattern=r"Fleet Management",
        scene_name="Logi-Only"
    )
    
    switcher.add_scene_rule(
        monitor=1,
        url_pattern=r"twitch\.tv",
        scene_name="Twitch Scene"
    )
    
    # Add more specific rules as needed
    switcher.add_scene_rule(
        monitor=0,
        url_pattern=r".*",  # Default rule for monitor 0
        scene_name="BRIO-Only"
    )
    
    # Start monitoring
    await switcher.monitor_chrome_windows()

if __name__ == "__main__":
    asyncio.run(main())
