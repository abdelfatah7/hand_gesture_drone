# ✋ Hand Gesture Drone Control
### ROS 2 · PX4 · MediaPipe · Gazebo

> Control a drone in simulation using only your webcam and hand gestures — no controller, no keyboard, no joystick.

<br>

![ROS2](https://img.shields.io/badge/ROS2-Humble-blue?logo=ros)
![PX4](https://img.shields.io/badge/PX4-SITL-orange)
![Python](https://img.shields.io/badge/Python-3.10-green?logo=python)
![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10.9-red)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## 📌 Overview

This project translates real-time hand gestures captured via a laptop webcam into drone flight commands using **Computer Vision** and **PX4 Offboard Control**.

The system runs two parallel components:
- A **gesture detection node** that reads the camera, tracks hand landmarks via MediaPipe, and classifies gestures
- A **drone controller node** that receives gesture commands and sends velocity setpoints to PX4 via ROS 2

Flight is controlled through **pure velocity setpoints** — the drone moves as long as a gesture is held and stops the moment it's released.

---

## 🖐️ Gesture Mapping

| Gesture | Action |
|--------|--------|
| ✋ Open hand (5 fingers) | Takeoff — continuous climb |
| ✊ Fist | Land — continuous descent |
| 👉 Index finger right | Move right |
| 👈 Index finger left | Move left |
| ☝️ Index finger up | Hover — stop in place |

---

## 🏗️ System Architecture

```
📷 Laptop Webcam
       │
       ▼
  MediaPipe Hand Tracking
  (21 landmarks per frame)
       │
       ▼
  Gesture Classifier
  (finger extension + direction logic)
       │
       ▼
  Smoothing Filter
  (12-frame majority vote)
       │
       ▼
  ROS 2 DroneController Node
       │
       ├──▶ /fmu/in/offboard_control_mode
       ├──▶ /fmu/in/trajectory_setpoint   ← velocity [vx, vy, vz]
       └──▶ /fmu/in/vehicle_command       ← ARM / mode switch
       │
       ▼
  PX4 SITL (via uXRCE-DDS Bridge)
       │
       ▼
  🚁 Gazebo Simulation (x500 model)
```

---

## 🛠️ Tech Stack

| Tool | Version | Purpose |
|------|---------|---------|
| ROS 2 | Humble | System communication framework |
| PX4 Autopilot | v1.14+ | Flight controller (SITL) |
| Gazebo | Harmonic | Physics simulation |
| MediaPipe | 0.10.9 | Hand landmark detection |
| OpenCV | 4.8+ | Camera capture and frame processing |
| uXRCE-DDS | — | ROS 2 ↔ PX4 bridge |
| px4_msgs | — | PX4 ROS 2 message definitions |
| Python | 3.10 | Implementation language |

---

## 📋 Prerequisites

Make sure the following are installed and working before proceeding:

- Ubuntu 22.04
- [ROS 2 Humble](https://docs.ros.org/en/humble/Installation.html)
- [PX4 Autopilot](https://docs.px4.io/main/en/dev_setup/dev_env_linux_ubuntu.html)
- [Gazebo Harmonic](https://gazebosim.org/docs/harmonic/install)
- [Micro XRCE-DDS Agent](https://docs.px4.io/main/en/middleware/uxrce_dds.html)
- [px4_msgs](https://github.com/PX4/px4_msgs) — must match your PX4 firmware version

---

## ⚙️ Installation

### 1. Clone into your ROS 2 workspace

```bash
cd ~/ros2_ws/src
git clone https://github.com/abdelfatah7/hand_gesture_drone.git
```

### 2. Install Python dependencies

```bash
cd ~/ros2_ws/src/hand_gesture_drone
pip install "numpy<2"
pip install mediapipe==0.10.9 opencv-python
```

> ⚠️ **Important:** `mediapipe==0.10.9` requires `numpy<2`. Installing in this order avoids conflicts.

### 3. Build the package

```bash
cd ~/ros2_ws
colcon build --packages-select hand_gesture_drone
source install/setup.bash
```

---

## 🚀 Running the Project

Open **4 separate terminals** and run each command:

**Terminal 1 — PX4 SITL + Gazebo**
```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

**Terminal 2 — uXRCE-DDS Bridge**
```bash
MicroXRCEAgent udp4 -p 8888
```

**Terminal 3 — Source and run**
```bash
source ~/ros2_ws/install/setup.bash
ros2 run hand_gesture_drone drone_controller
```

**Terminal 4 — Monitor (optional)**
```bash
ros2 topic echo /fmu/out/vehicle_status
```

Once the controller node starts, a webcam window opens. The drone arms and enters Offboard mode automatically after ~0.5 seconds.

---

## 📁 Package Structure

```
hand_gesture_drone/
├── hand_gesture_drone/
│   ├── __init__.py
│   ├── gesture_detector.py     # MediaPipe hand tracking + gesture classification
│   └── drone_controller.py     # ROS 2 node — velocity control + PX4 commands
├── resource/
│   └── hand_gesture_drone
├── package.xml
├── setup.py
├── setup.cfg
├── requirements.txt
└── README.md
```

---

## 🔧 Key Engineering Decisions

**Velocity control over position control**
Early versions used position setpoints which caused the drone to snap to fixed coordinates instead of moving smoothly. Switching to velocity setpoints means the drone moves continuously while a gesture is held and stops naturally when released.

**Gesture smoothing via majority vote**
Raw gesture classification fluctuates frame-to-frame. A 12-frame sliding window majority vote filter eliminates false triggers from accidental hand movement without adding noticeable latency.

**Re-arm after landing**
PX4 exits Offboard mode after landing. The controller detects this and automatically re-arms and re-enters Offboard when the next takeoff gesture is detected — no need to restart the node.

**No NAV_LAND command**
Using `VEHICLE_CMD_NAV_LAND` exits Offboard mode permanently in the same session. Instead, landing is handled by sending a downward velocity setpoint until the estimated altitude reaches zero.

---

## 📡 ROS 2 Topics

| Topic | Direction | Message Type | Description |
|-------|-----------|-------------|-------------|
| `/fmu/in/offboard_control_mode` | Publish | `OffboardControlMode` | Declares velocity control mode at 20 Hz |
| `/fmu/in/trajectory_setpoint` | Publish | `TrajectorySetpoint` | Velocity commands [vx, vy, vz] |
| `/fmu/in/vehicle_command` | Publish | `VehicleCommand` | ARM / mode switch commands |
| `/fmu/out/vehicle_status` | Subscribe | `VehicleStatus` | Monitor arming state and nav mode |

---

## 🐛 Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| `mediapipe has no attribute 'solutions'` | numpy version conflict | `pip install "numpy<2" mediapipe==0.10.9` |
| Drone doesn't take off | Not in Offboard mode | Wait for "OFFBOARD sent" in terminal before gesturing |
| Drone spins on ground after land | NAV_LAND exits Offboard | Already fixed in v6 — uses velocity landing |
| Gesture keeps switching | Poor lighting or hand too close | Improve lighting, keep hand 40–60 cm from camera |
| Camera not found | Wrong camera index | Change `camera_index=0` to `1` or `2` in `drone_controller.py` |

---

## 🔮 Future Work

- [ ] Add forward/backward control (2-finger gesture)
- [ ] Integrate with YOLOv8 for autonomous threat detection patrol
- [ ] Replace estimated altitude with actual PX4 altitude feedback
- [ ] Add gesture confirmation (hold N frames before executing LAND)
- [ ] Support real hardware via companion computer

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🙋 Author

**Abdelfattah Ahmed**
Aeronautical & Aerospace Engineering — New Mansoura University

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin)](https://linkedin.com/in/abdelfatah7)
[![GitHub](https://img.shields.io/badge/GitHub-abdelfatah7-black?logo=github)](https://github.com/abdelfatah7)
