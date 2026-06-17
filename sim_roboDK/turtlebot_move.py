from robodk import robolink
from robodk.robomath import *
import time
import math

RDK = robolink.Robolink()

# =========================
# RoboDK 아이템 이름
# =========================
turtle_base = RDK.Item("turtlebot Base")
red_box = RDK.Item("Red")

if not turtle_base.Valid():
    raise Exception("turtlebot Base를 찾을 수 없습니다. 이름을 확인하세요.")

# =========================
# 시작 위치 + 경유지 좌표
# [X, Y, Z]
# =========================
START = [1210, -2510, 20]

WAYPOINTS = [
    [2560, -1140, 20],   # Frame 5
    [-340, -780, 20],    # Frame 4
    [330, -380, 20],     # Frame 3
    [1960, -450, 20],    # Frame 2
    [2640, -20, 20],     # Frame 1
]

# =========================
# Red 박스를 터틀봇에 붙이기
# =========================
if red_box.Valid():
    red_abs_pose = red_box.PoseAbs()
    red_box.setParentStatic(turtle_base)
    red_box.setPoseAbs(red_abs_pose)
    print("Red 박스를 turtlebot Base에 붙였습니다.")
else:
    print("Red 박스를 찾지 못했습니다. 박스 없이 이동합니다.")

# =========================
# pose 생성 함수
# =========================
def make_pose(x, y, z, yaw_deg=0):
    """
    x, y, z 위치와 z축 회전각으로 RoboDK pose 생성
    yaw_deg: 터틀봇 방향 각도
    """
    return transl(x, y, z) * rotz(math.radians(yaw_deg))

# =========================
# 두 점 사이 방향각 계산
# =========================
def calc_yaw_deg(p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.degrees(math.atan2(dy, dx))

# =========================
# 부드러운 이동 함수
# =========================
def move_smooth(item, target_pose, speed=350, dt=0.03):
    start_pose = item.PoseAbs()

    start = Pose_2_TxyzRxyz(start_pose)
    target = Pose_2_TxyzRxyz(target_pose)

    dx = target[0] - start[0]
    dy = target[1] - start[1]
    dist = math.sqrt(dx * dx + dy * dy)

    steps = max(1, int(dist / (speed * dt)))

    for i in range(1, steps + 1):
        ratio = i / steps

        now = [
            start[j] + (target[j] - start[j]) * ratio
            for j in range(6)
        ]

        item.setPoseAbs(TxyzRxyz_2_Pose(now))
        RDK.Render()
        time.sleep(dt)

# =========================
# 실행
# =========================

# 1. 시작 위치로 세팅
start_yaw = calc_yaw_deg(START, WAYPOINTS[0])
turtle_base.setPoseAbs(make_pose(START[0], START[1], START[2], start_yaw))
RDK.Render()
time.sleep(0.5)

print("TurtleBot 이동 시작")

# 2. 경유지 순서대로 이동
current = START

for idx, wp in enumerate(WAYPOINTS):
    yaw = calc_yaw_deg(current, wp)
    target_pose = make_pose(wp[0], wp[1], wp[2], 0)

    print(f"Moving to Frame {5 - idx}: X={wp[0]}, Y={wp[1]}, Z={wp[2]}, Yaw={yaw:.1f}")
    move_smooth(turtle_base, target_pose, speed=350)

    current = wp

print("TurtleBot 이동 완료")