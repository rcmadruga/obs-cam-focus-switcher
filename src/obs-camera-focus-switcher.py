#!/usr/bin/env python3

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
class MonitorScene:
    monitor: int
    scene: str

@dataclass
class Application:
    name: str
    patterns: List[str]

@dataclass
class Config:
    monitor_scenes: List[MonitorScene]
    applications: List[Application]

class WindowInfo(NamedTuple):
    monitor: int
    title: str
    hwnd: int  # Window handle for checking focus
    last_active: float  # Timestamp of last activity

class WindowState(NamedTuple):
    monitor: int
    title: str
    scene: str
    hash: str

class OBSWindowSwitcher:
    def __init__(self, config_path: str = "etc/config.yaml", verbose: bool = False):
        self.verbose = verbose
        self.config_path = config_path
        self.config = self.load_config(config_path)
        self.ws = None
        self.current_scene: Optional[str] = None
        self.last_state_hash: Optional[str] = None

    def log(self, message):
        if self.verbose:
            print(message)     

    def load_config(self, config_path: str) -> Config:
        """Load and parse configuration file."""
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
            
        monitor_scenes = [
            MonitorScene(
                monitor=item['monitor'],
                scene=item['scene']
            )
            for item in raw_config['monitor_scenes']
        ]
        
        applications = [
            Application(
                name=app['name'],
                patterns=app['patterns']
            )
            for app in raw_config['applications']
        ]
        
        return Config(monitor_scenes=monitor_scenes, applications=applications)

    async def connect_obs(self):
        """Establish connection to OBS WebSocket server."""
        with open(self.config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
        
        obs_config = raw_config['obs_config']
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
            self.log(f"Initial scene: {self.current_scene}")

    def get_chrome_windows_info(self) -> List[WindowInfo]:
        """Get information about all visible Chrome windows including focus state."""
        windows_info = []
        foreground_hwnd = win32gui.GetForegroundWindow()
        
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
                            
                            # Set timestamp based on focus
                            last_active = time.time() if hwnd == foreground_hwnd else 0
                            
                            windows_info.append(WindowInfo(
                                monitor=monitor,
                                title=title,
                                hwnd=hwnd,
                                last_active=last_active
                            ))
                            self.log(f"Found window: Monitor {monitor}, Title: {title}, Focus: {hwnd == foreground_hwnd}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return True

        win32gui.EnumWindows(callback, None)
        return windows_info

    def is_matching_application(self, title: str) -> bool:
        """Check if the window title matches any application patterns."""
        for app in self.config.applications:
            for pattern in app.patterns:
                if re.search(pattern, title, re.IGNORECASE):
                    self.log(f"Matched application: {app.name} with pattern: {pattern}")
                    return True
        return False

    def get_scene_for_monitor(self, monitor: int) -> Optional[str]:
        """Get the configured scene name for a monitor."""
        for monitor_scene in self.config.monitor_scenes:
            if monitor_scene.monitor == monitor:
                return monitor_scene.scene
        return None

    def find_best_matching_window(self, windows: List[WindowInfo]) -> Optional[Tuple[int, str]]:
        """
        Find the best matching window based on application patterns and focus/activity.
        Returns (monitor, scene_name) tuple if found, None otherwise.
        """
        matching_windows = []
        
        # First, find all windows that match any application pattern
        for window in windows:
            if self.is_matching_application(window.title):
                scene = self.get_scene_for_monitor(window.monitor)
                if scene:
                    matching_windows.append((window, scene))
        
        if not matching_windows:
            return None
            
        # Sort matching windows by last_active timestamp (most recent first)
        matching_windows.sort(key=lambda x: x[0].last_active, reverse=True)
        
        # Return the monitor and scene for the most recently active window
        best_match = matching_windows[0]
        return (best_match[0].monitor, best_match[1])

    def create_state_hash(self, monitor: int, title: str, scene: Optional[str]) -> str:
        """Create a unique hash for the current state."""
        return f"{monitor}:{title}:{scene if scene else 'no_match'}"

    async def switch_scene(self, scene_name: str):
        """Switch OBS scene if it's different from current scene."""
        if scene_name != self.current_scene:
            self.log(f"Attempting to switch from {self.current_scene} to {scene_name}")
            request = simpleobsws.Request('SetCurrentProgramScene', {
                'sceneName': scene_name
            })
            response = await self.ws.call(request)
            if response.ok():
                self.current_scene = scene_name
                self.log(f"Successfully switched to {scene_name}")
                return True
            else:
                self.log(f"Failed to switch scene: {response}")
        return False

    async def monitor_chrome_windows(self, check_interval: float = 1.0):
        """Main loop to monitor Chrome windows and switch scenes."""
        self.log("Starting monitoring loop...")
        
        while True:
            windows = self.get_chrome_windows_info()
            
            # Find best matching window considering focus and activity
            best_match = self.find_best_matching_window(windows)
            
            if best_match:
                monitor, scene_name = best_match
                current_hash = self.create_state_hash(monitor, "active_window", scene_name)
                
                self.log(f"\nCurrent state:")
                self.log(f"Monitor: {monitor}")
                self.log(f"Scene: {scene_name}")
                self.log(f"Current hash: {current_hash}")
                self.log(f"Last hash: {self.last_state_hash}")
                
                if current_hash != self.last_state_hash:
                    self.log("State change detected!")
                    if await self.switch_scene(scene_name):
                        self.last_state_hash = current_hash
                        self.log(f"Updated state hash to: {self.last_state_hash}")
            else:
                current_hash = self.create_state_hash(0, "no_window", None)
                if current_hash != self.last_state_hash:
                    self.log("No matching windows found - keeping current scene")
                    self.last_state_hash = current_hash
            
            await asyncio.sleep(check_interval)

def get_monitor_at_point(x: int, y: int) -> int:
    """Get monitor number at given coordinates."""
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
        switcher = OBSWindowSwitcher(str(config_path), args.verbose)
        
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
