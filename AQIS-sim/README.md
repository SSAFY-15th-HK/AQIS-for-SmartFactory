# AQIS Simulation Workspace

`AQIS-sim` contains only simulation assets and the simulation monitoring web app.

## Structure

```text
AQIS-sim/
  robodk/
    AQIS.rdk
    Main.py
    box/
    conv/
    object/
    robot/
    tool/
  web/
    package.json
    src/
```

## RoboDK

- `robodk/AQIS.rdk`: RoboDK station file
- `robodk/Main.py`: RoboDK-side simulation script that talks to the FastAPI server

The script uses:

```text
http://localhost:8000
```

Start the FastAPI server before running `Main.py`.

## Web

The simulation dashboard lives in `web/`.

```bash
cd AQIS-sim/web
npm install
npm run dev -- --host 0.0.0.0
```

The web app is a monitoring-oriented animation for understanding process state. It is not intended to be frame-synchronized with RoboDK.

## RoboDK Assets

- `robot/UR5.robot`: Pick-and-place robot arm
- `tool/OnRobot-VG10-Vacuum-Gripper.tool`: Vacuum gripper tool
- `conv/Conveyor-Belt-2m.robot`: Conveyor model
- `robot/turtlebot3_waffle.step`: AGV/TurtleBot visual model
- `object/Red.step`, `Blue.step`, `Green.step`, `Yellow.step`: inspection parts
- `box/Bin-Blue.sld`: Normal bin
- `box/Bin-Red.sld`: Defect bin
- `object/path.step`: AGV route visual guide
- `object/Floor.sld`: Floor model

## Recommended Item Names

RoboDK scripts and the FastAPI adapter should use stable item names. In `AQIS.rdk`, keep or rename items to:

```text
UR5
OnRobot VG10 Vacuum Gripper
Conveyor Belt (2m) Base
MainFrame
turtlebot Base
Yellow
Red
Green
Blue
```
