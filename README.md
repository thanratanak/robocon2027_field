# robocon2027_field

ABU Robocon 2027 "The Pursuit of Mustika Nusantara" game field for **ROS 2 Jazzy + gz sim (Gazebo Harmonic)** and RViz2.
Built from Rulebook V1.1 and Appendix V1.1 (October 2026). Dimensions come straight from the Appendix drawings.

## Install
```bash
sudo apt install ros-jazzy-ros-gz-sim ros-jazzy-ros-gz-bridge ros-jazzy-robot-state-publisher ros-jazzy-rviz2
mkdir -p ~/ros2_ws/src && cp -r robocon2027_field ~/ros2_ws/src/
cd ~/ros2_ws && colcon build --packages-select robocon2027_field && source install/setup.bash
```

## Run
```bash
ros2 launch robocon2027_field gazebo.launch.py                     # field + 53 game objects in gz sim
ros2 launch robocon2027_field rviz.launch.py                       # field in RViz2 (frame: map)
ros2 launch robocon2027_field rviz.launch.py with_objects:=true    # + blocks and Mustika at start positions
```
Gazebo options: `objects:=false` (field only, no blocks or Mustika), `gz_args:="-r -s"` (no GUI), `bridge_clock:=false`.

## Coordinates
Origin = field centre on the ground. **+x toward Blue, -x toward Red, +y toward the Mustika Pillar end**
(Storage Areas are at +y, Start/Retry Zones and the Ground Shared Area at -y), z up. Units: metres.
The 11 m field is measured to the inner face of the Game Field Boundary. The RViz2 field hangs on TF frame `map`,
so your robot's `map` frame and the field frame are the same.

| Item | Where |
|---|---|
| Start/Retry Zones 700x700 | x = 4.0..4.7 and 4.8..5.5, y = -5.5..-4.8 (mirror for Red) |
| Storage Area 1000x2000 | x = 3.5..5.5, y = 4.5..5.5 |
| Ground Shared Area 1200x1200 (+ 5x5 grid of 200 mm) | centre (0, -4.25) |
| Mustika Pillar (500 high) | (0, 4.25) |
| Level 1 (top z = 0.6) | x, y = -3..3 |
| Transfer Area 1000x1000 | x = 3..4 (Blue), y = -1.8..-0.8, z = 0.6 |
| Stairs (3 x 150 mm) | x = 3..4, y = -2.7..-1.8 |
| Ramp (3500 long, smooth wedge mesh `meshes/ramp_wedge.stl`) | x = 3..4, from y = -0.8 (z 0.6) down to y = 2.7 (z 0) |
| L1 Retry Zones 700x700 | Blue x = 1.5..2.2, Red x = -2.2..-1.5, y = 2.27..2.97 |
| Level 2 (z 0.6..0.9, no stairs) | x, y = -1.5..1.5 |
| Central Pillar (top z = 1.7) | (0, 0) |

## Meshes
The ramp is the only mesh (`meshes/ramp_wedge.stl`, a plain wedge). `gazebo.launch.py` adds the package share folder to
`GZ_SIM_RESOURCE_PATH` so gz sim finds it. If you start gz sim by hand, run first:
`export GZ_SIM_RESOURCE_PATH=$GZ_SIM_RESOURCE_PATH:~/ros2_ws/install/robocon2027_field/share`

## How collision works
* Visual fences have the **real Appendix size** (boundary 50x100, dividers/L1 barrier 30x50 mm).
* In Gazebo each fence also gets an **invisible 300 mm tall collision box** (60 mm thick) with the same footprint and the
  same openings, so a robot cannot drive over a 50 mm wall. Openings are kept at: Ground Shared Area, Mustika Pillar area,
  L1 Shared Areas, Level 2, and both Transfer Areas. The L2 sides are plain steps: BR must climb 300 mm.
  Use `--proxy-height 0` when regenerating to get real-size collision only.
* The pillar receptacles (diameter 180 x 100 deep) are real concave shapes made of boxes, so the Mustika can sit in them.

## Game objects (gz sim)
20 + 20 Earth Blocks (0.35 m, 0.6 kg, stacked 2 high in the Storage Areas), 12 Sky Blocks (0.2 m, 0.22 kg, on their sides in the
grid, two-colour halves), 1 Mustika (radius 0.105 m, 0.27 kg) on the Mustika Pillar. They are normal dynamic models.
Reset with the gz GUI (Ctrl+R) or `gz service -s /world/robocon2027/control --reqtype gz.msgs.WorldControl --reptype gz.msgs.Boolean --timeout 3000 --req 'reset: {all: true}'`.

## Things to double-check
1. `SKY_LAYOUT` in `scripts/generate_field.py` was read by eye from Rulebook Figure 4. Compare and edit the table if needed.
2. The Mustika Pillar is placed at the centre of its 1000x1000 shared area (Appendix Fig 3.2d looks centred).
3. Earth/Sky Block and Mustika colours are approximations of the photos in the Appendix.
4. Storage Areas are drawn strong red/blue (like Rulebook Figures 1 and 3). Rulebook Section 14 says they have the ground
   colour; regenerate with `--storage-official` if you want that.

## Regenerate
Edit `scripts/generate_field.py`, then `python3 scripts/generate_field.py` (needs python3-matplotlib only for the preview),
and rebuild the package. `docs/field_plan.png` is the generated top view.
