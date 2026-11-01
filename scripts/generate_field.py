#!/usr/bin/env python3
"""
ABU Robocon 2027 field generator  (Rulebook V1.1 + Appendix V1.1)

Writes:
  worlds/robocon2027.sdf              Gazebo (gz sim) world, field + all game objects
  worlds/robocon2027_field_only.sdf   same world without Earth Blocks, Sky Blocks and Mustika
  urdf/field.urdf                     RViz2 model, field only
  urdf/field_with_objects.urdf        RViz2 model, field + objects at start positions
  docs/field_plan.png                 top view, for checking against Appendix Fig 3.1

Coordinates (meters): origin = field centre on the ground,
  +x toward the BLUE side, +y toward the Mustika Pillar end, z up.
The 11000 mm field is measured to the INNER face of the Game Field Boundary.

Usage:  python3 scripts/generate_field.py [--proxy-height 0.30] [--storage-official]
"""
import argparse
import math
import os

# ----------------------------------------------------------------------------
# Colors (Rulebook Section 14, RGB 0-255). Blocks/Mustika are approximations.
# ----------------------------------------------------------------------------
C = {
    'ground_red': (240, 210, 210), 'ground_blue': (170, 210, 230),
    'shared': (245, 240, 200),
    'zone_red': (223, 34, 34), 'zone_blue': (50, 0, 255),
    'stairs_red': (235, 180, 160), 'stairs_blue': (150, 215, 220),
    'ramp_red': (200, 150, 140), 'ramp_blue': (130, 180, 200),
    'l1_red': (235, 180, 160), 'l1_blue': (150, 215, 220),
    'spot': (40, 100, 50),
    'transfer_red': (245, 170, 60), 'transfer_blue': (60, 170, 245),
    'grey': (190, 190, 185), 'brown': (100, 62, 0),
    'grid_light': (255, 252, 215), 'grid_grey': (205, 205, 200),
    'grid_center': (120, 75, 20),
    'earth_red': (225, 40, 40), 'earth_blue': (50, 70, 200),
    'sky_red': (225, 40, 40), 'sky_blue': (35, 45, 150),
    'mustika': (255, 184, 28),
}

# ----------------------------------------------------------------------------
# Sky Block start layout, read from Rulebook Figure 4 (row 1 = top = +y,
# column 1 = left = Red side). Each block lies on its side; the code says which
# colour half points where:  'R_N' = red half to north (+y) / blue to south,
# 'B_N' = blue half north, 'R_W' = red half to west (-x) / blue east, 'B_W' =
# blue half west.  CHECK THIS TABLE AGAINST FIGURE 4 and edit if needed.
# ----------------------------------------------------------------------------
SKY_LAYOUT = {
    (1, 1): 'R_N', (1, 3): 'R_W', (1, 5): 'B_N',
    (2, 2): 'B_W', (2, 4): 'B_W',
    (3, 1): 'B_N', (3, 5): 'R_N',
    (4, 2): 'R_W', (4, 4): 'R_W',
    (5, 1): 'R_N', (5, 3): 'B_W', (5, 5): 'B_N',
}

# Earth Block / Sky Block / Mustika physical values (Rulebook V1.1, Appendix)
EARTH_SIZE, EARTH_MASS = 0.35, 0.60
SKY_SIZE, SKY_MASS = 0.20, 0.22
MUSTIKA_R, MUSTIKA_MASS = 0.105, 0.27


class Builder:
    def __init__(self, proxy_h, storage_official):
        self.parts = []      # static field geometry
        self.objs = []       # dynamic game objects
        self.proxy_h = proxy_h
        self.storage_official = storage_official
        self._names = set()

    # -- low level ---------------------------------------------------------
    def _uniq(self, name):
        assert name not in self._names, 'duplicate name ' + name
        self._names.add(name)
        return name

    def box(self, name, cx, cy, cz, sx, sy, sz, color, vis=True, col=True, rpy=(0, 0, 0)):
        self.parts.append(dict(name=self._uniq(name), type='box', pose=(cx, cy, cz) + tuple(rpy),
                               size=(sx, sy, sz), color=color, vis=vis, col=col))

    def cyl(self, name, cx, cy, cz, r, h, color, vis=True, col=True):
        self.parts.append(dict(name=self._uniq(name), type='cylinder', pose=(cx, cy, cz, 0, 0, 0),
                               size=(r, h), color=color, vis=vis, col=col))

    def mesh(self, name, fname, cx, cy, cz, color):
        self.parts.append(dict(name=self._uniq(name), type='mesh', pose=(cx, cy, cz, 0, 0, 0),
                               size=(1, 1, 1), color=color, vis=True, col=False, mesh=fname))

    def flat(self, name, cx, cy, sx, sy, zbase, layer, color):
        """Thin painted marking, visual only. Higher layer = drawn on top."""
        self.box(name, cx, cy, zbase + 0.001 * (layer + 1), sx, sy, 0.002, color, col=False)

    def fence(self, name, cx, cy, sx, sy, zbase, vh, color, proxy=None):
        """Real-size visual. If proxy=(pcx,pcy,psx,psy) and proxy_h>0, the collision is a
        taller invisible box instead (so a robot cannot ride over a 50 mm wall)."""
        if proxy is not None and self.proxy_h > 0:
            self.box(name, cx, cy, zbase + vh / 2, sx, sy, vh, color, col=False)
            pcx, pcy, psx, psy = proxy
            self.box(name + '_proxy', pcx, pcy, zbase + self.proxy_h / 2, psx, psy, self.proxy_h,
                     color, vis=False, col=True)
        else:
            self.box(name, cx, cy, zbase + vh / 2, sx, sy, vh, color, col=True)

    def ring(self, name, cx, cy, zc, h, ri, ro, n, color):
        """Hollow collar made of n boxes (concave receptacle)."""
        rm = (ri + ro) / 2.0
        c = 2 * ro * math.sin(math.pi / n) + 0.002
        for k in range(n):
            a = 2 * math.pi * k / n
            self.box('%s_%02d' % (name, k), cx + rm * math.cos(a), cy + rm * math.sin(a), zc,
                     ro - ri, c, h, color, rpy=(0, 0, a))

    def pillar(self, name, cx, cy, zbase, height):
        """Pillar diameter 270 with receptacle diameter 180 x 100 deep."""
        solid = height - 0.10
        self.cyl(name + '_body', cx, cy, zbase + solid / 2, 0.135, solid, 'brown')
        self.ring(name + '_rim', cx, cy, zbase + solid + 0.05, 0.10, 0.09, 0.135, 24, 'brown')

    # -- the field ----------------------------------------------------------
    def build_field(self):
        # ground
        for s, t in ((1, 'blue'), (-1, 'red')):
            self.box('ground_' + t, s * 2.75, 0, -0.01, 5.5, 11.0, 0.02, 'ground_' + t, col=False)
        self.box('ground_collision', 0, 0, -0.1, 11.2, 11.2, 0.2, 'ground_red', vis=False)

        # Game Field Boundary (50 wide x 100 tall), outside the +-5.5 square
        b, bh = 0.05, 0.10
        for s, n in ((1, 'n'), (-1, 's')):
            self.fence('boundary_' + n, 0, s * (5.5 + b / 2), 11.0 + 2 * b, b, 0, bh, 'brown',
                       proxy=(0, s * (5.5 + 0.05), 11.2, 0.10))
        for s, n in ((1, 'e'), (-1, 'w')):
            self.fence('boundary_' + n, s * (5.5 + b / 2), 0, b, 11.0, 0, bh, 'brown',
                       proxy=(s * (5.5 + 0.05), 0, 0.10, 11.0))

        # Center Divider (ground) 30 x 50, on x = 0, with openings
        for i, (y0, y1) in enumerate([(-5.5, -4.85), (-3.65, -3.0), (3.0, 3.75), (4.75, 5.5)]):
            ln, cy = y1 - y0, (y0 + y1) / 2
            self.fence('divider_ground_%d' % i, 0, cy, 0.03, ln, 0, 0.05, 'brown',
                       proxy=(0, cy, 0.06, ln))

        # Start/Retry zones, Storage areas
        for s, t in ((1, 'blue'), (-1, 'red')):
            for k, x in enumerate((4.35, 5.15)):
                self.flat('startretry_%s_%d' % (t, k), s * x, -5.15, 0.7, 0.7, 0, 0, 'zone_' + t)
            col = 'ground_' + t if self.storage_official else 'zone_' + t
            self.flat('storage_' + t, s * 4.5, 5.0, 2.0, 1.0, 0, 0, col)

        # Ground Shared Area with the 5x5 Sky Block grid (200 mm cells)
        self.flat('ground_shared', 0, -4.25, 1.2, 1.2, 0, 0, 'shared')
        for r in range(1, 6):
            for c in range(1, 6):
                x, y = (c - 3) * 0.2, -4.25 + (3 - r) * 0.2
                if (r, c) == (3, 3):
                    col = 'grid_center'
                elif (r + c) % 2 == 0:
                    col = 'grid_light'
                else:
                    col = 'grid_grey'
                self.flat('gsa_cell_%d%d' % (r, c), x, y, 0.196, 0.196, 0, 1, col)

        # Mustika Pillar area (1000 x 1000) and pillar
        self.flat('mustika_area', 0, 4.25, 1.0, 1.0, 0, 0, 'shared')
        self.pillar('mustika_pillar', 0, 4.25, 0.0, 0.5)

        # Level 1 platform (outer 6000 x 6000, top at 600). Floor inside = 5940 x 5940.
        self.box('l1_platform', 0, 0, 0.3, 6.0, 6.0, 0.6, 'grey')
        for s, t in ((1, 'blue'), (-1, 'red')):
            self.flat('l1_floor_' + t, s * 1.485, 0, 2.97, 5.94, 0.6, 0, 'l1_' + t)
            self.flat('l1_retry_' + t, s * 1.85, 2.62, 0.7, 0.7, 0.6, 1, 'zone_' + t)
        for sy in (1, -1):
            self.flat('l1_shared_%d' % sy, 0, sy * 2.595, 1.0, 0.75, 0.6, 1, 'shared')
            self.flat('l1_spot_center_%d' % sy, 0, sy * 2.72, 0.5, 0.5, 0.6, 2, 'spot')
            for sx in (1, -1):
                self.flat('l1_spot_%d_%d' % (sx, sy), sx * 2.72, sy * 2.72, 0.5, 0.5, 0.6, 2, 'spot')

        # L1 Perimeter Barrier 30 x 50 on the outer edge, open at the two Transfer Areas
        for s, n in ((1, 'n'), (-1, 's')):
            self.fence('l1_barrier_' + n, 0, s * 2.985, 6.0, 0.03, 0.6, 0.05, 'grey',
                       proxy=(0, s * 2.97, 6.0, 0.06))
        for s, n in ((1, 'e'), (-1, 'w')):
            for k, (y0, y1) in enumerate([(-2.97, -1.8), (-0.8, 2.97)]):
                ln, cy = y1 - y0, (y0 + y1) / 2
                self.fence('l1_barrier_%s%d' % (n, k), s * 2.985, cy, 0.03, ln, 0.6, 0.05, 'grey',
                           proxy=(s * 2.97, cy, 0.06, ln))
        # Center Divider (L1) 30 x 50
        for i, (y0, y1) in enumerate([(-2.22, -1.5), (1.5, 2.22)]):
            ln, cy = y1 - y0, (y0 + y1) / 2
            self.fence('l1_divider_%d' % i, 0, cy, 0.03, ln, 0.6, 0.05, 'brown',
                       proxy=(0, cy, 0.06, ln))

        # Stairs, Transfer Area, Ramp (outside the L1 left/right edges, x = 3..4)
        theta = math.atan2(0.6, 3.5)
        for s, t in ((1, 'blue'), (-1, 'red')):
            xc = s * 3.5
            for k in (1, 2, 3):
                y0 = -2.7 + 0.3 * (k - 1)
                self.box('stair_%s_%d' % (t, k), xc, y0 + 0.15, 0.075 * k, 1.0, 0.3, 0.15 * k, 'stairs_' + t)
            self.box('transfer_body_' + t, xc, -1.3, 0.3, 1.0, 1.0, 0.6, 'stairs_' + t)
            self.flat('transfer_' + t, xc, -1.3, 1.0, 1.0, 0.6, 0, 'transfer_' + t)
            # ramp visual: one smooth wedge mesh (meshes/ramp_wedge.stl), y -0.8 .. 2.7
            self.mesh('ramp_' + t, 'ramp_wedge.stl', xc, 0.95, 0, 'ramp_' + t)
            # ramp collision: smooth thick slab on the slope + coarse fillers underneath
            L, th = math.hypot(3.5, 0.6), 0.04
            ymid, zmid = 0.95, 0.30
            self.box('ramp_slab_' + t, xc, ymid - (th / 2) * math.sin(theta), zmid - (th / 2) * math.cos(theta),
                     1.0, L, th, 'ramp_' + t, vis=False, rpy=(-theta, 0, 0))
            for i in range(14):
                y0, y1 = -0.8 + 0.25 * i, -0.8 + 0.25 * (i + 1)
                h = max(0.6 * (2.7 - y1) / 3.5 - 0.045, 0.005)
                self.box('ramp_fill_%s_%02d' % (t, i), xc, (y0 + y1) / 2, h / 2, 1.0, 0.25, h,
                         'ramp_' + t, vis=False)

        # Level 2 (3000 x 3000, 600..900), no stairs, plus building spots and Central Pillar
        self.box('l2_platform', 0, 0, 0.75, 3.0, 3.0, 0.3, 'grey')
        for sx in (1, -1):
            for sy in (1, -1):
                self.flat('l2_spot_%d_%d' % (sx, sy), sx * 1.25, sy * 1.25, 0.5, 0.5, 0.9, 0, 'spot')
        self.pillar('central_pillar', 0, 0, 0.9, 0.8)

    # -- game objects -------------------------------------------------------
    def build_objects(self):
        # 20 Earth Blocks per team in the Storage Area: 10 columns of 2
        for s, t in ((1, 'blue'), (-1, 'red')):
            n = 0
            for j in range(10):
                i, row = j % 5, j // 5
                x, y = s * (3.7 + 0.4 * i), 4.775 + 0.45 * row
                for lvl in (0, 1):
                    n += 1
                    self.objs.append(dict(name='earth_%s_%02d' % (t, n), kind='earth', team=t,
                                          pose=(x, y, 0.175 + 0.35 * lvl + 0.002 * (lvl + 1), 0, 0, 0)))
        # 12 Sky Blocks on their sides in the 5x5 grid.
        # Local +z half of the block is BLUE: Rx(+90) puts blue to -y (red north);
        # Rx(-90) blue north; Ry(+90) puts blue to +x (red west); Ry(-90) blue to -x (blue west)
        rpy = {'R_N': (math.pi / 2, 0, 0), 'B_N': (-math.pi / 2, 0, 0),
               'R_W': (0, math.pi / 2, 0), 'B_W': (0, -math.pi / 2, 0)}
        for (r, c), code in sorted(SKY_LAYOUT.items()):
            x, y = (c - 3) * 0.2, -4.25 + (3 - r) * 0.2
            self.objs.append(dict(name='sky_%d%d' % (r, c), kind='sky', team=None,
                                  pose=(x, y, 0.101) + rpy[code]))
        # Mustika seated on the Mustika Pillar (rim at z=0.5, receptacle radius 0.09)
        zc = 0.5 + math.sqrt(MUSTIKA_R ** 2 - 0.09 ** 2) + 0.002
        self.objs.append(dict(name='mustika_01', kind='mustika', team=None, pose=(0, 4.25, zc, 0, 0, 0)))


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def rgba(key, a=1.0):
    r, g, b = C[key]
    return '%.4f %.4f %.4f %.1f' % (r / 255.0, g / 255.0, b / 255.0, a)


def f(v):
    return ('%.5f' % v).rstrip('0').rstrip('.') if abs(v) > 1e-9 else '0'


def pose_str(p):
    return ' '.join(f(v) for v in p)


def rot(rpy):
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr]]


def mul(R, v):
    return [sum(R[i][j] * v[j] for j in range(3)) for i in range(3)]


def sky_halves(pose):
    """Two half-boxes (red, blue) of a Sky Block in WORLD frame (for URDF / preview)."""
    x, y, z, r, p, yw = pose
    R = rot((r, p, yw))
    out = []
    for key, off in (('sky_red', -0.05), ('sky_blue', 0.05)):
        d = mul(R, (0, 0, off))
        out.append((key, (x + d[0], y + d[1], z + d[2], r, p, yw)))
    return out


# ----------------------------------------------------------------------------
# SDF (gz sim)
# ----------------------------------------------------------------------------
def geom_sdf(p):
    if p['type'] == 'mesh':
        return '<mesh><uri>model://robocon2027_field/meshes/%s</uri></mesh>' % p['mesh']
    if p['type'] == 'box':
        return '<box><size>%s %s %s</size></box>' % tuple(f(v) for v in p['size'])
    return '<cylinder><radius>%s</radius><length>%s</length></cylinder>' % tuple(f(v) for v in p['size'])


def mat_sdf(key):
    return '<material><ambient>%s</ambient><diffuse>%s</diffuse><specular>0.05 0.05 0.05 1</specular></material>' % (
        rgba(key), rgba(key))


def write_sdf(B, path, with_objects=True):
    L = []
    a = L.append
    a('<?xml version="1.0"?>')
    a('<!-- GENERATED by scripts/generate_field.py - edit the script, not this file. -->')
    a('<sdf version="1.9">')
    a('  <world name="robocon2027">')
    a('    <physics name="1ms" type="ignored"><max_step_size>0.001</max_step_size><real_time_factor>1.0</real_time_factor></physics>')
    for fn, nm in (('gz-sim-physics-system', 'gz::sim::systems::Physics'),
                   ('gz-sim-user-commands-system', 'gz::sim::systems::UserCommands'),
                   ('gz-sim-scene-broadcaster-system', 'gz::sim::systems::SceneBroadcaster'),
                   ('gz-sim-imu-system', 'gz::sim::systems::Imu')):
        a('    <plugin filename="%s" name="%s"/>' % (fn, nm))
    a('    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors"><render_engine>ogre2</render_engine></plugin>')
    a('    <gravity>0 0 -9.81</gravity>')
    a('    <scene><ambient>0.5 0.5 0.5 1</ambient><background>0.75 0.8 0.85 1</background><shadows>true</shadows></scene>')
    a('    <light type="directional" name="sun"><cast_shadows>true</cast_shadows><pose>0 0 10 0 0 0</pose>'
      '<diffuse>0.9 0.9 0.9 1</diffuse><specular>0.2 0.2 0.2 1</specular><direction>-0.4 0.3 -0.9</direction></light>')
    a('    <model name="robocon_field">')
    a('      <static>true</static>')
    a('      <link name="field_link">')
    for p in B.parts:
        if p['vis']:
            a('        <visual name="%s_v"><pose>%s</pose><geometry>%s</geometry>%s</visual>' % (
                p['name'], pose_str(p['pose']), geom_sdf(p), mat_sdf(p['color'])))
        if p['col']:
            a('        <collision name="%s_c"><pose>%s</pose><geometry>%s</geometry></collision>' % (
                p['name'], pose_str(p['pose']), geom_sdf(p)))
    a('      </link>')
    a('    </model>')

    fric = '<surface><friction><ode><mu>0.6</mu><mu2>0.6</mu2></ode></friction></surface>'

    def inertial(m, ixx, iyy, izz):
        return ('<inertial><mass>%s</mass><inertia><ixx>%s</ixx><iyy>%s</iyy><izz>%s</izz>'
                '<ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia></inertial>') % (f(m), f(ixx), f(iyy), f(izz))

    for o in (B.objs if with_objects else []):
        a('    <model name="%s">' % o['name'])
        a('      <pose>%s</pose>' % pose_str(o['pose']))
        a('      <link name="link">')
        if o['kind'] == 'earth':
            s = EARTH_SIZE
            i = EARTH_MASS * (2 * s * s) / 12.0
            a('        ' + inertial(EARTH_MASS, i, i, i))
            a('        <collision name="c"><geometry><box><size>%s %s %s</size></box></geometry>%s</collision>' % (f(s), f(s), f(s), fric))
            a('        <visual name="v"><geometry><box><size>%s %s %s</size></box></geometry>%s</visual>' % (
                f(s), f(s), f(s), mat_sdf('earth_' + o['team'])))
        elif o['kind'] == 'sky':
            s = SKY_SIZE
            i = SKY_MASS * (2 * s * s) / 12.0
            a('        ' + inertial(SKY_MASS, i, i, i))
            a('        <collision name="c"><geometry><box><size>%s %s %s</size></box></geometry>%s</collision>' % (f(s), f(s), f(s), fric))
            for key, zoff in (('sky_red', -0.05), ('sky_blue', 0.05)):
                a('        <visual name="v_%s"><pose>0 0 %s 0 0 0</pose><geometry><box><size>%s %s 0.1</size></box></geometry>%s</visual>' % (
                    key, f(zoff), f(s), f(s), mat_sdf(key)))
        else:
            r = MUSTIKA_R
            i = 2.0 / 3.0 * MUSTIKA_MASS * r * r      # thin-shell sphere
            a('        ' + inertial(MUSTIKA_MASS, i, i, i))
            a('        <collision name="c"><geometry><sphere><radius>%s</radius></sphere></geometry>'
              '<surface><friction><ode><mu>0.8</mu><mu2>0.8</mu2></ode></friction></surface></collision>' % f(r))
            a('        <visual name="v"><geometry><sphere><radius>%s</radius></sphere></geometry>%s</visual>' % (f(r), mat_sdf('mustika')))
        a('      </link>')
        a('    </model>')
    a('  </world>')
    a('</sdf>')
    open(path, 'w').write('\n'.join(L) + '\n')


# ----------------------------------------------------------------------------
# URDF (RViz2)
# ----------------------------------------------------------------------------
def write_urdf(B, path, with_objects):
    L = []
    a = L.append
    a('<?xml version="1.0"?>')
    a('<!-- GENERATED by scripts/generate_field.py - edit the script, not this file. -->')
    a('<robot name="robocon2027_field">')
    used = set(p['color'] for p in B.parts if p['vis'])
    if with_objects:
        used |= {'earth_red', 'earth_blue', 'sky_red', 'sky_blue', 'mustika'}
    for key in sorted(used):
        a('  <material name="%s"><color rgba="%s"/></material>' % (key, rgba(key)))
    a('  <link name="field">')

    def vis(name, kind, pose, dims, color, mesh=None):
        if kind == 'mesh':
            g = '<mesh filename="package://robocon2027_field/meshes/%s"/>' % mesh
        elif kind == 'box':
            g = '<box size="%s %s %s"/>' % tuple(f(v) for v in dims)
        elif kind == 'cylinder':
            g = '<cylinder radius="%s" length="%s"/>' % tuple(f(v) for v in dims)
        else:
            g = '<sphere radius="%s"/>' % f(dims[0])
        a('    <visual name="%s"><origin xyz="%s" rpy="%s"/><geometry>%s</geometry><material name="%s"/></visual>' % (
            name, ' '.join(f(v) for v in pose[:3]), ' '.join(f(v) for v in pose[3:]), g, color))

    for p in B.parts:
        if p['vis']:
            vis(p['name'], p['type'], p['pose'], p['size'], p['color'], p.get('mesh'))
    if with_objects:
        for o in B.objs:
            if o['kind'] == 'earth':
                vis(o['name'], 'box', o['pose'], (EARTH_SIZE,) * 3, 'earth_' + o['team'])
            elif o['kind'] == 'sky':
                for k, (key, pz) in enumerate(sky_halves(o['pose'])):
                    vis('%s_%d' % (o['name'], k), 'box', pz, (SKY_SIZE, SKY_SIZE, 0.1), key)
            else:
                vis(o['name'], 'sphere', o['pose'], (MUSTIKA_R,), 'mustika')
    a('  </link>')
    a('</robot>')
    open(path, 'w').write('\n'.join(L) + '\n')


# ----------------------------------------------------------------------------
# ramp wedge mesh (ASCII STL): 1.0 wide (x), 3.5 long (y), 0.6 high at y=-1.75 sloping to 0 at y=+1.75
# ----------------------------------------------------------------------------
def write_ramp_stl(path):
    A0, A1, B0, B1 = (-.5, -1.75, 0), (.5, -1.75, 0), (-.5, 1.75, 0), (.5, 1.75, 0)
    T0, T1 = (-.5, -1.75, .6), (.5, -1.75, .6)
    tris = [(A0, B1, A1), (A0, B0, B1),          # bottom (-z)
            (T0, B1, B0), (T0, T1, B1),          # sloped top (+z)
            (A0, A1, T1), (A0, T1, T0),          # high end wall (-y)
            (A0, T0, B0),                        # left side (-x)
            (A1, B1, T1)]                        # right side (+x)
    out = ['solid ramp_wedge']
    for a, b, c in tris:
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        ln = math.sqrt(sum(k * k for k in n)) or 1.0
        out.append(' facet normal %.6f %.6f %.6f' % tuple(k / ln for k in n))
        out.append('  outer loop')
        for q in (a, b, c):
            out.append('   vertex %.6f %.6f %.6f' % q)
        out.append('  endloop')
        out.append(' endfacet')
    out.append('endsolid ramp_wedge')
    open(path, 'w').write('\n'.join(out) + '\n')


# ----------------------------------------------------------------------------
# plan-view preview
# ----------------------------------------------------------------------------
def write_plan(B, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Circle
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_aspect('equal')
    items = [p for p in B.parts if p['vis'] and p['type'] == 'box'
             and abs(p['pose'][3]) < 1e-6 and abs(p['pose'][4]) < 1e-6 and abs(p['pose'][5]) < 1e-6]
    items.sort(key=lambda p: p['pose'][2] + p['size'][2] / 2)
    for p in items:
        x, y, z = p['pose'][:3]
        sx, sy, sz = p['size']
        c = tuple(v / 255.0 for v in C[p['color']])
        ax.add_patch(Rectangle((x - sx / 2, y - sy / 2), sx, sy, fc=c, ec='none', lw=0))
    for p in B.parts:
        if p['vis'] and p['type'] == 'mesh':
            x, y = p['pose'][:2]
            ax.add_patch(Rectangle((x - .5, y - 1.75), 1.0, 3.5, fc=tuple(v / 255.0 for v in C[p['color']]), ec='none'))
    for p in B.parts:
        if p['vis'] and p['type'] == 'cylinder':
            ax.add_patch(Circle(p['pose'][:2], p['size'][0], fc=tuple(v / 255 for v in C[p['color']]), ec='k', lw=0.5))
    for o in B.objs:
        x, y = o['pose'][:2]
        if o['kind'] == 'earth':
            ax.add_patch(Rectangle((x - .175, y - .175), .35, .35, fc=tuple(v / 255 for v in C['earth_' + o['team']]), ec='k', lw=0.4))
        elif o['kind'] == 'sky':
            ax.add_patch(Rectangle((x - .1, y - .1), .2, .2, fc='none', ec='k', lw=0.6))
            for key, pz in sky_halves(o['pose']):
                ax.add_patch(Circle(pz[:2], 0.035, fc=tuple(v / 255 for v in C[key]), ec='none'))
        else:
            ax.add_patch(Circle((x, y), MUSTIKA_R, fc=tuple(v / 255 for v in C['mustika']), ec='k', lw=0.5))
    ax.set_xlim(-5.8, 5.8)
    ax.set_ylim(-5.8, 5.8)
    ax.set_xlabel('x [m]   (Red <-  -> Blue)')
    ax.set_ylabel('y [m]   (Start zones <-  -> Mustika Pillar)')
    ax.set_title('ABU Robocon 2027 field, plan view (generated)')
    ax.grid(True, lw=0.3, alpha=0.4)
    fig.savefig(path, dpi=110, bbox_inches='tight')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proxy-height', type=float, default=0.30,
                    help='height (m) of invisible collision boxes behind the real-size fences; 0 = real collision only')
    ap.add_argument('--storage-official', action='store_true',
                    help='paint Storage Areas with the Section 14 ground colour instead of strong red/blue')
    ap.add_argument('--no-plan', action='store_true')
    a = ap.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    B = Builder(a.proxy_height, a.storage_official)
    B.build_field()
    B.build_objects()
    os.makedirs(os.path.join(root, 'meshes'), exist_ok=True)
    write_ramp_stl(os.path.join(root, 'meshes', 'ramp_wedge.stl'))
    write_sdf(B, os.path.join(root, 'worlds', 'robocon2027.sdf'))
    write_sdf(B, os.path.join(root, 'worlds', 'robocon2027_field_only.sdf'), with_objects=False)
    write_urdf(B, os.path.join(root, 'urdf', 'field.urdf'), False)
    write_urdf(B, os.path.join(root, 'urdf', 'field_with_objects.urdf'), True)
    if not a.no_plan:
        write_plan(B, os.path.join(root, 'docs', 'field_plan.png'))
    print('parts: %d  objects: %d' % (len(B.parts), len(B.objs)))


if __name__ == '__main__':
    main()
