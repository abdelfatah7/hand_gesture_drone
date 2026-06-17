import math
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

from px4_msgs.msg import (
    VehicleCommand,
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleStatus,
)

import cv2
import threading
import time

from hand_gesture_drone.gesture_detector import HandGestureDetector, GestureCommand


PX4_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)

# velocity mapping لكل gesture (vx, vy, vz) — NED: vz سالب=صعود موجب=نزول
GESTURE_VELOCITY = {
    GestureCommand.TAKEOFF:    (0.0,  0.0, -1.2),   # صعود مستمر
    GestureCommand.MOVE_RIGHT: (0.0,  1.5,  0.0),   # يمين
    GestureCommand.MOVE_LEFT:  (0.0, -1.5,  0.0),   # يسار
    GestureCommand.HOVER:      (0.0,  0.0,  0.0),   # ثبات
    GestureCommand.NONE:       (0.0,  0.0,  0.0),   # ثبات
    GestureCommand.LAND:       (0.0,  0.0,  0.8),   # نزول مستمر
}


class DroneController(Node):

    OFFBOARD_HZ = 20
    LAND_STOP_ALT = 0.05   # متر — لما يوصل هنا يوقف المحركات

    def __init__(self):
        super().__init__("hand_gesture_drone_controller")

        self.pub_cmd      = self.create_publisher(VehicleCommand,      "/fmu/in/vehicle_command",       PX4_QOS)
        self.pub_offboard = self.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", PX4_QOS)
        self.pub_setpoint = self.create_publisher(TrajectorySetpoint,  "/fmu/in/trajectory_setpoint",   PX4_QOS)
        self.create_subscription(VehicleStatus, "/fmu/out/vehicle_status", self._status_cb, PX4_QOS)

        self.nav_state          = VehicleStatus.NAVIGATION_STATE_MANUAL
        self.offboard_counter   = 0
        self.armed_and_offboard = False
        self.is_armed           = False
        self.is_on_ground       = True

        # الـ velocity الحالي اللي بيتبعت لـ PX4
        self._vx = 0.0
        self._vy = 0.0
        self._vz = 0.0

        # تقدير الارتفاع (للـ auto-disarm عند الهبوط)
        self.est_alt = 0.0

        # الـ gesture الحالي
        self.current_cmd = GestureCommand.NONE

        # cooldown للـ LAND بس عشان ميتحولش عن طريق الخطأ
        self.land_locked    = False
        self.last_land_time = 0.0

        self.create_timer(1.0 / self.OFFBOARD_HZ, self._control_loop)

        self.detector    = HandGestureDetector(camera_index=0, smoothing_window=12, show_debug=True)
        self._stop_event = threading.Event()
        threading.Thread(target=self._gesture_loop, daemon=True).start()

        self.get_logger().info("Ready | 5fingers=Up | Fist=Down/Land | Index=Move | IndexUp=Hover")

    def _status_cb(self, msg):
        self.nav_state = msg.nav_state
        self.is_armed  = (msg.arming_state == VehicleStatus.ARMING_STATE_ARMED)

    # ── Control loop ─────────────────────────────────────────────────────────
    def _control_loop(self):
        dt = 1.0 / self.OFFBOARD_HZ

        # ARM + OFFBOARD مرة واحدة في البداية
        self._pub_offboard_mode()
        if self.offboard_counter == 10 and not self.armed_and_offboard:
            self._set_offboard_mode()
            self._arm()
            self.armed_and_offboard = True
        self.offboard_counter += 1

        cmd = self.current_cmd

        # لو على الأرض ومش TAKEOFF — صفر velocity وخلاص
        if self.is_on_ground and cmd != GestureCommand.TAKEOFF:
            self._vx = self._vy = self._vz = 0.0
            self._pub_setpoint()
            return

        # لو LAND وعلى الأرض — وقف
        if cmd == GestureCommand.LAND and self.est_alt <= self.LAND_STOP_ALT:
            self._vx = self._vy = self._vz = 0.0
            self.is_on_ground = True
            self.est_alt      = 0.0
            self.land_locked  = False
            self.get_logger().info("GROUNDED")
            self._pub_setpoint()
            return

        # طبق الـ velocity من الـ gesture مباشرة
        vx, vy, vz = GESTURE_VELOCITY.get(cmd, (0.0, 0.0, 0.0))
        self._vx = vx
        self._vy = vy
        self._vz = vz

        # تحديث الارتفاع المقدر
        self.est_alt -= vz * dt   # vz NED: موجب=نزول يعني est_alt بينقص

        # لو كان على الأرض وبدأ يطلع
        if self.is_on_ground and vz < 0:
            self.is_on_ground = False
            self.get_logger().info("AIRBORNE")

        self._pub_setpoint()

    # ── Publishers ────────────────────────────────────────────────────────────
    def _pub_offboard_mode(self):
        msg             = OffboardControlMode()
        msg.timestamp   = self._ts()
        msg.position    = False
        msg.velocity    = True
        msg.acceleration= False
        msg.attitude    = False
        msg.body_rate   = False
        self.pub_offboard.publish(msg)

    def _pub_setpoint(self):
        msg           = TrajectorySetpoint()
        msg.timestamp = self._ts()
        msg.position  = [math.nan, math.nan, math.nan]
        msg.velocity  = [self._vx, self._vy, self._vz]
        msg.yaw       = 0.0
        self.pub_setpoint.publish(msg)

    # ── Commands ──────────────────────────────────────────────────────────────
    def _send_vehicle_command(self, command, param1=0.0, param2=0.0):
        msg                  = VehicleCommand()
        msg.timestamp        = self._ts()
        msg.command          = command
        msg.param1           = param1
        msg.param2           = param2
        msg.target_system    = 1
        msg.target_component = 1
        msg.source_system    = 1
        msg.source_component = 1
        msg.from_external    = True
        self.pub_cmd.publish(msg)

    def _arm(self):
        self._send_vehicle_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, param1=1.0)
        self.get_logger().info("ARM sent")

    def _set_offboard_mode(self):
        self._send_vehicle_command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, param1=1.0, param2=6.0)
        self.get_logger().info("OFFBOARD sent")

    def _rearm(self):
        self._set_offboard_mode()
        time.sleep(0.3)
        self._arm()

    # ── Gesture handler ───────────────────────────────────────────────────────
    def _handle_gesture(self, cmd: GestureCommand):
        now = time.time()

        # LAND محتاج confirmation — لازم يفضل قبضة لمدة > 0.5 ثانية
        if cmd == GestureCommand.LAND:
            if not self.land_locked:
                if (now - self.last_land_time) < 0.5:
                    # فاضل شوية — اطبق LAND
                    self.land_locked = True
                    self.current_cmd = GestureCommand.LAND
                    self.get_logger().info("LANDING...")
                else:
                    self.last_land_time = now
            # لو land_locked خليه
            return

        # أي gesture تاني يفك الـ land lock
        self.land_locked = False

        # لو على الأرض وعايز يقلع — re-arm لو محتاج
        if cmd == GestureCommand.TAKEOFF and self.is_on_ground:
            if self.nav_state != 14:
                self._rearm()
                time.sleep(0.4)

        self.current_cmd = cmd

    # ── Camera loop ───────────────────────────────────────────────────────────
    def _gesture_loop(self):
        self.get_logger().info("Camera loop started")
        state_color = {
            GestureCommand.TAKEOFF:    (0,   220, 0),
            GestureCommand.LAND:       (0,   80,  255),
            GestureCommand.MOVE_RIGHT: (255, 165, 0),
            GestureCommand.MOVE_LEFT:  (0,   165, 255),
            GestureCommand.HOVER:      (255, 255, 0),
            GestureCommand.NONE:       (120, 120, 120),
        }
        while not self._stop_event.is_set():
            cmd, frame = self.detector.get_frame_gesture()
            self._handle_gesture(cmd)
            if frame is not None:
                status = "ON GROUND" if self.is_on_ground else f"AIRBORNE {self.est_alt:.1f}m"
                color  = (120, 120, 120) if self.is_on_ground else (0, 255, 0)
                cv2.putText(frame, status,
                            (15, frame.shape[0] - 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
                cv2.imshow("Hand Gesture Drone Control", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self._stop_event.set()
                    rclpy.shutdown()
                    break
        self.detector.release()

    def _ts(self):
        return self.get_clock().now().nanoseconds // 1000

    def destroy_node(self):
        self._stop_event.set()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = DroneController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()