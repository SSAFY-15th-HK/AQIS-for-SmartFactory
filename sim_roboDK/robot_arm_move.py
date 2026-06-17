from robodk import robolink
import time

RDK = robolink.Robolink()

# =========================
# RoboDK 아이템 찾기
# =========================
robot = RDK.Item("UR5")
tool = RDK.Item("OnRobot VG10 Vacuum Gripper")
red_box = RDK.Item("Red")
turtle_base = RDK.Item("turtlebot Base")

home = RDK.Item("Home")
target2 = RDK.Item("Target 2")   # Pick 위치
target3 = RDK.Item("Target 3")   # 이동 중간 위치
target4 = RDK.Item("Target 4")   # Place 위치

def check(item, name):
    if not item.Valid():
        raise Exception(f"'{name}' 을 찾을 수 없습니다. 왼쪽 트리 이름을 확인하세요.")

check(robot, "UR5")
check(tool, "OnRobot VG10 Vacuum Gripper")
check(red_box, "Red")
check(turtle_base, "turtlebot Base")
check(home, "Home")
check(target2, "Target 2")
check(target3, "Target 3")
check(target4, "Target 4")

# 속도 조절
robot.setSpeed(100)

# =========================
# Pick & Place 동작
# =========================

print("1. Home 이동")
robot.MoveJ(home)

print("2. Pick 위치 Target 2 이동")
robot.MoveJ(target2)
time.sleep(0.5)

print("3. Red 흡착")
red_abs = red_box.PoseAbs()
red_box.setParentStatic(tool)
red_box.setPoseAbs(red_abs)
time.sleep(0.5)

print("4. Target 3 이동")
robot.MoveJ(target3)

print("5. Place 위치 Target 4 이동")
robot.MoveJ(target4)
time.sleep(0.5)

print("6. Red를 터틀봇 위에 놓기")
red_abs = red_box.PoseAbs()
red_box.setParentStatic(turtle_base)
red_box.setPoseAbs(red_abs)
time.sleep(0.5)

print("7. Target 3 복귀")
robot.MoveJ(target3)

print("8. Home 복귀")
robot.MoveJ(home)

# 터틀봇 출발 신호
RDK.setParam("LOAD_READY", "1")

print("Pick & Place 완료")
