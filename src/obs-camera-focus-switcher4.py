import win32gui
import win32process
import psutil
import asyncio
import simpleobsws
import time
import re
import yaml
import argparse
from typing import Dict, Optional, List, Tuple, NamedTuple
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SceneRule:
    monitor: int
    url_pattern: str
    scene_name: str

class WindowState(NamedTuple):
    monitor: int
    title: str
    scene: str
    hash: str

class OBSWindowSwitcher:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self.load_config(config_path)
        self.ws = None
        self.scene_rules: List[SceneRule] = []
        self.current_scene: Optional[str] = None
        self.last_state_hash: Optional[str] = None
        
        # Load rules from config
        self.load_rules_from_config()
        
    def load_config(self, config_path: str) -> dict:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
            
    def load_rules_from_config(self):
        self.scene_rules.clear()
        
        def add_rules_from_section(section):
            if section in self.config['rules']:
                for rule_group in self.config['rules'][section]:
                    for pattern in rule_group['patterns']:
                        self.add_scene_rule(
                            monitor=rule_group['monitor_id'],
                            url_pattern=pattern,
                            scene_name=rule_group['scene_name']
                        )
        
        # Add rules from all sections
        add_rules_from_section('meeting_rules')
        add_rules_from_section('streaming_rules')
        add_rules_from_section('software_rules')
        
    async def connect_obs(self):
        obs_config = self.config['obs_config']
        self.ws = simpleobsws.WebSocketClient(
            url=obs_config['url'],
            password=obs_config['password']
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
        rule = SceneRule(monitor, url_pattern, scene_name)
        self.scene_rules.append(rule)

    def get_chrome_windows_info(self) -> List[Tuple[int, str]]:
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
                            print(f"Found window: Monitor {monitor}, Title: {title}")
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

    def create_state_hash(self, monitor: int, title: str, scene: Optional[str]) -> str:
        """Create a unique hash for the current state."""
        return f"{monitor}:{title}:{scene if scene else 'no_match'}"

    async def switch_scene(self, scene_name: str):
        if scene_name != self.current_scene:
            print(f"Attempting to switch from {self.current_scene} to {scene_name}")
            request = simpleobsws.Request('SetCurrentProgramScene', {
                'sceneName': scene_name
            })
            response = await self.ws.call(request)
            if response.ok():
                self.current_scene = scene_name
                print(f"Successfully switched to {scene_name}")
                return True
            else:
                print(f"Failed to switch scene: {response}")
        return False

    async def monitor_chrome_windows(self, check_interval: float = 1.0):
        print("Starting monitoring loop...")
        
        while True:
            windows = self.get_chrome_windows_info()
            
            for monitor, title in windows:
                scene_name = self.find_matching_scene(monitor, title)
                current_hash = self.create_state_hash(monitor, title, scene_name)
                
                print(f"\nCurrent state:")
                print(f"Monitor: {monitor}")
                print(f"Title: {title}")
                print(f"Scene: {scene_name if scene_name else 'No match - keeping current scene'}")
                print(f"Current hash: {current_hash}")
                print(f"Last hash: {self.last_state_hash}")
                
                if current_hash != self.last_state_hash:
                    print("State change detected!")
                    if scene_name:  # Only switch scene if we have a match
                        if await self.switch_scene(scene_name):
                            self.last_state_hash = current_hash
                            print(f"Updated state hash to: {self.last_state_hash}")
                    else:
                        print("No matching rule found - keeping current scene")
                        self.last_state_hash = current_hash
                break
            
            await asyncio.sleep(check_interval)

def get_monitor_at_point(x: int, y: int) -> int:
    import win32api
    
    monitors = win32api.EnumDisplayMonitors()
    for i, (handle, device, rect) in enumerate(monitors):
        if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
            return i
    return 0

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='OBS Window Scene Switcher')
    parser.add_argument(
        '-c', '--config',
        default='etc/config.yaml',
        help='Path to configuration file (default: etc/config.yaml)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    return parser.parse_args()

async def main():
    # Parse command line arguments
    args = parse_arguments()
    
    # Check if config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        print("Please create a config file or specify the correct path using --config")
        return 1
        
    try:
        # Initialize the window switcher with config file
        switcher = OBSWindowSwitcher(str(config_path))
        
        # Connect to OBS
        await switcher.connect_obs()
        
        # Start monitoring
        await switcher.monitor_chrome_windows()
        
    except yaml.YAMLError as e:
        print(f"Error parsing config file: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        exit(0)
