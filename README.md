# OBS Camera Focus Switcher

OBS Camera Focus Switcher is a Python application that automatically switches OBS scenes based on the active Chrome window. This is useful for streamers or presenters who want to dynamically change scenes based on the content they are displaying.

## Features

- Monitors active Chrome windows.
- Switches OBS scenes based on predefined patterns.
- Configurable check interval.
- Verbose logging for debugging.

## Requirements

- Python 3.7+
- OBS Studio
- `simpleobsws` library for OBS WebSocket communication
- `asyncio` for asynchronous operations

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/obs-camera-focus-switcher.git
    cd obs-camera-focus-switcher
    ```

2. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

3. Configure OBS WebSocket:
    - Install the OBS WebSocket plugin from [here](https://github.com/obsproject/obs-websocket).
    - Enable the WebSocket server in OBS settings.

## Configuration

Create a configuration file [config.json](http://_vscodecontentref_/1) with the following structure:

```json
{
    "monitor_scenes": [
        {
            "monitor": 0,
            "scene": "Scene1"
        },
        {
            "monitor": 1,
            "scene": "Scene2"
        }
    ],
    "applications": [
        {
            "name": "Chrome",
            "patterns": ["Chrome", "Google Chrome"]
        }
    ]
}

Sure, here's a sample 

README.md

 file for the OBS Camera Focus Switcher project:

```markdown
# OBS Camera Focus Switcher

OBS Camera Focus Switcher is a Python application that automatically switches OBS scenes based on the active Chrome window. This is useful for streamers or presenters who want to dynamically change scenes based on the content they are displaying.

## Features

- Monitors active Chrome windows.
- Switches OBS scenes based on predefined patterns.
- Configurable check interval.
- Verbose logging for debugging.

## Requirements

- Python 3.7+
- OBS Studio
- `simpleobsws` library for OBS WebSocket communication
- `asyncio` for asynchronous operations

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/obs-camera-focus-switcher.git
    cd obs-camera-focus-switcher
    ```

2. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

3. Configure OBS WebSocket:
    - Enable the WebSocket server in OBS settings.

## Configuration

Create a configuration file 

config.json

 with the following structure:

```
# OBS WebSocket Configuration
obs_config:
  url: "ws://localhost:4455"
  password: "your_password_here"

# Direct monitor to scene mapping
monitor_scenes:
  - monitor: 0
    scene: "Scene A"    # Any matched application on monitor 0 triggers this scene
  - monitor: 1
    scene: "Scene B"     # Any matched application on monitor 1 triggers this scene

# Application patterns to match
applications:
  - name: "Google Meet"
    patterns:
      - "meet\\.google\\.com/[a-z|-]+"
      - "Google Meet.*Meeting"
      - "Meet - "
  - name: "Zoom"
    patterns:
      - "zoom\\.us/j/\\d+"
      - "Zoom Meeting"
      - "Zoom Webinar"
  - name: "Microsoft Teams"
    patterns:
      - "teams\\.microsoft\\.com/.*meeting"
      - "teams\\.live\\.com"
      - "Microsoft Teams.*Meeting"
      - "Meeting in.*Teams"
```

- `monitor_scenes`: List of monitors and their corresponding scenes.
- `applications`: List of applications and their title patterns to match.

## Usage

Run the application with the following command:

```sh
python obs-camera-focus-switcher5.py --config config.json --verbose
```

- `--config`: Path to the configuration file.
- `--verbose`: Enable verbose logging for debugging.

## Example

```sh
python obs-camera-focus-switcher.py --config config.json --verbose
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

This `README.md` file provides an overview of the project, installation instructions, configuration details, usage examples, and contribution guidelines. Adjust the content as needed to fit your specific project details.
