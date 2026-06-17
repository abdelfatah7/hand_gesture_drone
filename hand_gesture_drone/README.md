# 🚁 Hand Gesture Drone Control
## ROS 2 + PX4 + MediaPipe

---

## الـ Architecture

```
📷 Laptop Camera
       ↓
  MediaPipe (Hand Tracking)
       ↓
  Gesture Classifier
       ↓
  ROS 2 Node (drone_controller)
       ↓
  PX4 via uXRCE-DDS
       ↓
  🚁 Drone
```

---

## الـ Gestures

| الإيماءة | الأمر | الوصف |
|----------|-------|-------|
| ✋ يد مفتوحة (5 أصابع) | TAKEOFF | الإقلاع |
| ✊ قبضة مغلقة (0 أصابع) | LAND | الهبوط |
| 👉 سبابة يمين | MOVE RIGHT | تحرك يمين |
| 👈 سبابة يسار | MOVE LEFT | تحرك يسار |
| ☝️ سبابة لأعلى | HOVER | ثبات في الهواء |

---

## خطوات التثبيت والتشغيل

### 1. تثبيت المتطلبات Python
```bash
cd ~/ros2_ws/src/hand_gesture_drone
pip install -r requirements.txt
```

### 2. بناء الباكدج
```bash
cd ~/ros2_ws
colcon build --packages-select hand_gesture_drone
source install/setup.bash
```

### 3. تشغيل PX4 SITL (Gazebo)
```bash
# Terminal 1 - PX4 SITL
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

### 4. تشغيل uXRCE-DDS Bridge
```bash
# Terminal 2
MicroXRCEAgent udp4 -p 8888
```

### 5. تشغيل نود التحكم
```bash
# Terminal 3
source ~/ros2_ws/install/setup.bash
ros2 run hand_gesture_drone drone_controller
```

---

## التسلسل الزمني عند التشغيل

```
t=0s   → النود يبدأ، الكاميرا تشتغل
t=0.5s → يبدأ إرسال offboard heartbeat لـ PX4
t=0.5s → بعد 10 heartbeats يرسل ARM + OFFBOARD mode تلقائياً
t=1s   → وريه ✋ → يطلع لفوق لـ 2.5 متر
t=Xs   → وريه 👉 / 👈 → بيتحرك يمين/شمال
t=Xs   → وريه ✊ → يهبط
```

---

## تعديل الإعدادات (في drone_controller.py)

```python
LATERAL_SPEED   = 1.5      # سرعة اليمين/الشمال (m/s)
CRUISE_ALTITUDE = -2.5     # ارتفاع الإقلاع (NED، سالب = فوق) 
CMD_COOLDOWN    = 1.5      # ثواني بين كل أمر وأمر
OFFBOARD_HZ     = 20       # Hz للـ heartbeat
```

---

## استكشاف الأخطاء

| المشكلة | الحل |
|---------|------|
| الكاميرا مش شغالة | غير `camera_index=0` إلى `1` أو `2` |
| PX4 مش بيستقبل | تأكد MicroXRCEAgent شغال `MicroXRCEAgent udp4 -p 8888` |
| الدرون مش بيقلع | تأكد px4_msgs version متطابق مع PX4 firmware |
| الإيماءة مش بتتعرف | حسّن الإضاءة، خلي يدك واضحة في الكاميرا |
| False positives كتير | زود `smoothing_window` في gesture_detector.py |

---

## ملاحظة على الـ NED Frame

```
PX4 يستخدم NED (North-East-Down):
  x+ = شمال (forward)
  y+ = شرق (right)  
  z+ = تحت (down) → عشان كده الارتفاع سالب
```

---

## للدرون الحقيقي (بدل SITL)

نفس الكود بالظبط — بس:
1. تأكد MicroXRCEAgent موصل على الـ companion computer
2. غير `target_system=1` لـ sys_id الدرون الحقيقي
3. ابدأ بـ `LATERAL_SPEED = 0.5` للأمان
