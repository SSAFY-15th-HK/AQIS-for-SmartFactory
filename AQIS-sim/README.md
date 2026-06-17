# AQIS RoboDK Digital Twin Assets

이 폴더는 AQIS for SmartFactory의 RoboDK 기반 Digital Twin 시뮬레이션 에셋입니다.

## Main Station

- `AQIS.rdk`: RoboDK station file

## Assets

- `robot/UR5.robot`: Pick-and-place robot arm
- `tool/OnRobot-VG10-Vacuum-Gripper.tool`: Vacuum gripper tool
- `conv/Conveyor-Belt-2m.robot`: Conveyor model
- `robot/turtlebot3_waffle.step`: AGV/TurtleBot visual model
- `object/Red.step`, `Blue.step`, `Green.step`, `Yellow.step`: RGBY inspection parts
- `box/Bin-Blue.sld`: Normal bin
- `box/Bin-Red.sld`: Defect bin
- `object/path.step`: AGV route visual guide
- `object/Floor.sld`: Floor model

## Recommended RoboDK Item Names

RoboDK scripts and the FastAPI adapter should use stable item names. In `AQIS.rdk`, keep or rename items to:

```text
UR5
VacuumGripper
Conveyor
AGV
NormalBin
DefectBin
Part_Red
Part_Blue
Part_Green
Part_Yellow
AGV_Path
Floor
```

## Recommended Targets

```text
PART_SPAWN
PART_INSPECTION
PART_PICK

ROBOT_HOME
PICK_APPROACH
PICK
NORMAL_APPROACH
NORMAL_PLACE
DEFECT_APPROACH
DEFECT_PLACE

AGV_HOME
AGV_PICKUP
AGV_DROPOFF
AGV_RETURN
```

## Integration Direction

The current FastAPI server has a mock RoboDK adapter at:

```text
server/app/adapters/robodk.py
```

Next step is to replace the mock adapter methods with RoboDK Python API calls that open/use `AQIS.rdk` and run RoboDK programs such as:

```text
Sim_Start
Sim_Stop
Sort_Normal
Sort_Defect
AGV_Dispatch
Run_Demo_Sequence
```
