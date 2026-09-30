# This example is not working in Spyder directly (F5 or Run)
# Please type '!python turtle_runaway.py' on IPython console in your Spyder.
import tkinter as tk
import turtle, random, time, math
import base64, struct, zlib
import os, sys, shutil, subprocess

# ---------------------------------------------------------------------------
# Screen: everything is drawn on a 240 x 240 grid of 3 x 3 pixel "dots"
# ---------------------------------------------------------------------------
DOT = 3                         # one pixel-art dot = 3 x 3 screen pixels
VIEW = 240                      # the screen is VIEW x VIEW dots
SIZE = DOT * VIEW               # 720 x 720 screen pixels
FRAME_MSEC = 33                 # about 30 frames per second

# Arena geometry in dots; the centre of the sand floor is the turtle origin (0, 0)
R_IN, R_OUT = 90, 98            # inner / outer radius of the stone wall
FACE_IN, FACE_OUT = 5, 8        # visible height of the inner wall / outer facade
CX, CY = VIEW // 2, VIEW // 2 - FACE_IN   # centre of the wall circle
MOVE_R = (R_IN - 11) * DOT      # the turtles' feet must stay inside this circle
FOOT = 9 * DOT                  # a sprite is drawn 9 dots above its feet
START_X, START_Y = 180, -60     # start positions of the turtles (turtle coordinates)

# Palette (ENDESGA 32)
INK, NAVY, SLATE, STEEL, GRAY, SILVER, WHITE = '#181425', '#262b44', '#3a4466', '#5a6988', '#8b9bb4', '#c0cbdc', '#ffffff'
RED_D, RED, PINK = '#a22633', '#e43b44', '#f6757a'
BLUE_D, BLUE, CYAN = '#124e89', '#0099db', '#2ce8f5'
TEAL, GRASS_D, GRASS, GRASS_L = '#193c3e', '#265c42', '#3e8948', '#63c74d'
SAND_L, SAND, CLAY, SAND_D = '#ead4aa', '#e4a672', '#c28569', '#b86f50'
RUST, ORANGE, GOLD, YELLOW = '#be4a2f', '#f77622', '#feae34', '#fee761'
BROWN, PLUM, PURPLE, MAGENTA, SKIN = '#733e39', '#3e2731', '#68386c', '#b55088', '#e8b796'

# ---------------------------------------------------------------------------
# Pixel-art toolkit
# ---------------------------------------------------------------------------
class Bitmap:
    '''A small grid of dots; each dot is a color string or None (transparent).'''
    def __init__(self, w, h, fill=None):
        self.w, self.h = w, h
        self.px = [[fill] * w for _ in range(h)]

    def get(self, x, y):
        return self.px[y][x] if 0 <= x < self.w and 0 <= y < self.h else None

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = color

    def rect(self, x, y, w, h, color):
        for j in range(y, y + h):
            for i in range(x, x + w):
                self.set(i, j, color)

    def blit(self, src, ox, oy):
        for j, row in enumerate(src.px):
            for i, color in enumerate(row):
                if color is not None:
                    self.set(ox + i, oy + j, color)

    def copy(self):
        dup = Bitmap(self.w, self.h)
        dup.px = [row[:] for row in self.px]
        return dup

    def mirrored(self):
        dup = Bitmap(self.w, self.h)
        dup.px = [row[::-1] for row in self.px]
        return dup

    def outline(self, color, diagonal=False):
        '''Paint a 1-dot border around the opaque dots.'''
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if diagonal:
            dirs += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        border = [(x, y) for y in range(self.h) for x in range(self.w)
                  if self.px[y][x] is None and any(self.get(x + dx, y + dy) is not None for dx, dy in dirs)]
        for x, y in border:
            self.px[y][x] = color
        return self

    def drop_shadow(self, color, depth=1):
        solid = [(x, y) for y in range(self.h) for x in range(self.w) if self.px[y][x] is not None]
        for x, y in solid:
            for k in range(1, depth + 1):
                if y + k < self.h and self.px[y + k][x] is None:
                    self.px[y + k][x] = color
        return self

    def photo(self, scale=DOT):
        '''Convert to a Tk image, enlarged so that one dot becomes scale x scale pixels.
        A color may have an alpha part ('#rrggbbaa') to make it see-through.'''
        if any(c is not None and len(c) == 9 for row in self.px for c in row):
            img = tk.PhotoImage(data=self.png(), format='png')
        else:
            img = tk.PhotoImage(width=self.w, height=self.h)
            self.put_into(img)
        return img.zoom(scale) if scale > 1 else img

    def png(self):
        '''Encode as a base64 PNG with an alpha channel (Tk reads it on every version).'''
        def rgba(c):
            return bytes(4) if c is None else bytes.fromhex(c[1:] + ('ff' if len(c) == 7 else ''))
        raw = b''.join(b'\x00' + b''.join(rgba(c) for c in row) for row in self.px)
        chunk = lambda tag, data: struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data))
        png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', self.w, self.h, 8, 6, 0, 0, 0))
               + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
        return base64.b64encode(png)

    def put_into(self, img):
        if all(c is not None for row in self.px for c in row):
            img.put(' '.join('{' + ' '.join(row) + '}' for row in self.px))
        else:
            for y, row in enumerate(self.px):
                x = 0
                while x < self.w:
                    color = row[x]
                    if color is None:
                        x += 1
                        continue
                    x0 = x
                    while x < self.w and row[x] == color:
                        x += 1
                    img.put(color, to=(x0, y, x, y + 1))

def sprite(rows, legend):
    '''Build a Bitmap from strings; '.' is transparent and other chars are looked up in legend.'''
    b = Bitmap(len(rows[0]), len(rows))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != '.':
                b.px[y][x] = legend[ch]
    return b

def blob(cx, cy, rx, ry, power=2.0):
    '''Dots inside a rounded shape given in dot units (power 2 = ellipse, larger = boxier).'''
    return {(x, y) for y in range(math.floor(cy - ry) - 1, math.ceil(cy + ry) + 1)
                   for x in range(math.floor(cx - rx) - 1, math.ceil(cx + rx) + 1)
                   if abs((x + 0.5 - cx) / rx) ** power + abs((y + 0.5 - cy) / ry) ** power <= 1}

def ellipse(cx, cy, rx, ry):
    return blob(cx, cy, rx, ry)

def lit(cx, cy, rx, ry, light, base, dark):
    '''Shade a round part as if the light comes from the upper left.'''
    def color(x, y):
        d = 0.6 * (x + 0.5 - cx) / rx + 0.8 * (y + 0.5 - cy) / ry
        return light if d < -0.5 else dark if d > 0.4 else base
    return color

def paint(b, mask, color, line=INK):
    '''Draw a part with its own outline, so overlapping parts stay readable.'''
    if line:
        for x, y in mask:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (x + dx, y + dy) not in mask:
                    b.set(x + dx, y + dy, line)
    for x, y in mask:
        b.set(x, y, color(x, y) if callable(color) else color)

# ---------------------------------------------------------------------------
# Pixel font (5 x 7 dots per letter)
# ---------------------------------------------------------------------------
FONT_DATA = '''
A .###. #...# #...# ##### #...# #...# #...#
B ####. #...# #...# ####. #...# #...# ####.
C .###. #...# #.... #.... #.... #...# .###.
D ####. #...# #...# #...# #...# #...# ####.
E ##### #.... #.... ####. #.... #.... #####
F ##### #.... #.... ####. #.... #.... #....
G .###. #...# #.... #.### #...# #...# .####
H #...# #...# #...# ##### #...# #...# #...#
I .###. ..#.. ..#.. ..#.. ..#.. ..#.. .###.
J ..### ...#. ...#. ...#. #..#. #..#. .##..
K #...# #..#. #.#.. ##... #.#.. #..#. #...#
L #.... #.... #.... #.... #.... #.... #####
M #...# ##.## #.#.# #.#.# #...# #...# #...#
N #...# #...# ##..# #.#.# #..## #...# #...#
O .###. #...# #...# #...# #...# #...# .###.
P ####. #...# #...# ####. #.... #.... #....
Q .###. #...# #...# #...# #.#.# #..#. .##.#
R ####. #...# #...# ####. #.#.. #..#. #...#
S .#### #.... #.... .###. ....# ....# ####.
T ##### ..#.. ..#.. ..#.. ..#.. ..#.. ..#..
U #...# #...# #...# #...# #...# #...# .###.
V #...# #...# #...# #...# #...# .#.#. ..#..
W #...# #...# #...# #.#.# #.#.# #.#.# .#.#.
X #...# #...# .#.#. ..#.. .#.#. #...# #...#
Y #...# #...# .#.#. ..#.. ..#.. ..#.. ..#..
Z ##### ....# ...#. ..#.. .#... #.... #####
0 .###. #...# #..## #.#.# ##..# #...# .###.
1 ..#.. .##.. ..#.. ..#.. ..#.. ..#.. .###.
2 .###. #...# ....# ...#. ..#.. .#... #####
3 ####. ....# ....# .###. ....# ....# ####.
4 ...#. ..##. .#.#. #..#. ##### ...#. ...#.
5 ##### #.... ####. ....# ....# #...# .###.
6 ..##. .#... #.... ####. #...# #...# .###.
7 ##### ....# ...#. ..#.. .#... .#... .#...
8 .###. #...# #...# .###. #...# #...# .###.
9 .###. #...# #...# .#### ....# ...#. .##..
! ..#.. ..#.. ..#.. ..#.. ..#.. ..... ..#..
? .###. #...# ....# ...#. ..#.. ..... ..#..
. ..... ..... ..... ..... ..... ..... ..#..
, ..... ..... ..... ..... ..... ..#.. .#...
: ..... ..#.. ..#.. ..... ..#.. ..#.. .....
- ..... ..... ..... .###. ..... ..... .....
+ ..... ..#.. ..#.. ##### ..#.. ..#.. .....
/ ....# ....# ...#. ..#.. .#... #.... #....
' ..#.. ..#.. .#... ..... ..... ..... .....
> .#... ..#.. ...#. ....# ...#. ..#.. .#...
< ...#. ..#.. .#... #.... .#... ..#.. ...#.
'''
FONT = {' ': ['.....'] * 7}
for _line in FONT_DATA.strip().splitlines():
    _ch, *_rows = _line.split()
    FONT[_ch] = _rows

def text_bitmap(text, color, scale=1, outline=None, shadow=None):
    '''Render text with the pixel font; `color` may be a list of 7 colors (one per glyph row).'''
    rows = color if isinstance(color, list) else [color] * 7
    pad = 1 if outline else 0
    depth = max(1, scale // 2) if shadow else 0
    b = Bitmap(len(text) * 6 * scale - scale + 2 * pad, 7 * scale + 2 * pad + depth)
    for i, ch in enumerate(text.upper()):
        for gy, line in enumerate(FONT.get(ch, FONT['?'])):
            for gx, bit in enumerate(line):
                if bit == '#':
                    b.rect(pad + (i * 6 + gx) * scale, pad + gy * scale, scale, scale, rows[gy])
    if outline:
        b.outline(outline, diagonal=True)
    if shadow:
        b.drop_shadow(shadow, depth)
    return b

# ---------------------------------------------------------------------------
# Sprites: turtles, effects and UI parts
# ---------------------------------------------------------------------------
TEAM = {'blue': (CYAN, BLUE, BLUE_D), 'red': (PINK, RED, RED_D)}
SPR = 22                        # a turtle sprite is SPR x SPR dots
GROUND = 20                     # row of the sprite where the feet touch the ground

def draw_shell(b, cx, top, bottom, rx, colors, plate_dx=0.0):
    '''A dome-shaped shell with a hexagon plate pattern.'''
    light, base, dark = colors
    h = bottom - top
    dome = {p for p in blob(cx, bottom, rx, h, 2.4) if p[1] < bottom}
    top_row = min(y for _, y in dome)
    if sum(1 for _, y in dome if y == top_row) < 4:                 # no lonely dots on the top
        dome = {p for p in dome if p[1] != top_row}
    paint(b, dome, lit(cx, bottom - h * 0.6, rx, h * 0.7, light, base, dark))
    # Central plate outlined by darker seams, with seams running down to the rim
    pcx, pcy = cx + plate_dx, top + h * 0.5
    plate = blob(pcx, pcy, rx * 0.42, h * 0.3, 2.6)
    seams = {p for p in plate if any((p[0] + dx, p[1] + dy) not in plate for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    left, right = min(x for x, _ in plate), max(x for x, _ in plate)
    low = max(y for _, y in plate)
    for y in range(low, bottom):
        seams.add((left - 1, y))
        seams.add((right + 1, y))
    for x, y in seams:
        if (x, y) in dome:
            b.set(x, y, dark)
    # Shine on the upper left
    for x, y in ((math.floor(cx - rx * 0.62), math.floor(top + h * 0.35)),
                 (math.floor(cx - rx * 0.62), math.floor(top + h * 0.35) + 1)):
        if (x, y) in dome:
            b.set(x, y, WHITE)
    return dome

def turtle_bitmap(team, view, step=0, hop=0, pose='walk'):
    '''Draw a turtle. view: right/left/down/up, pose: walk/cheer/hide.'''
    colors = TEAM[team]
    b = Bitmap(SPR, SPR)
    paint(b, ellipse(11, GROUND, 7, 1.5), CLAY, line=None)          # shadow on the sand
    g = GROUND - hop                                                # body baseline
    skin = lambda cx, cy, rx, ry: paint(b, ellipse(cx, cy, rx, ry), lit(cx, cy, rx, ry, GRASS_L, GRASS_L, GRASS))
    rim = lambda cx, cy, rx, ry: paint(b, ellipse(cx, cy, rx, ry), lit(cx, cy, rx, ry, SAND_L, SAND_L, CLAY))
    angry = (team == 'red')

    if pose == 'hide':                                              # hidden in the shell
        draw_shell(b, 11, g - 13, g - 4, 7.5, colors)
        rim(11, g - 4, 8, 2.2)
        paint(b, ellipse(11, g - 3.5, 3.5, 1.3), INK, line=None)    # peeking eyes
        b.set(9, g - 4, WHITE); b.set(12, g - 4, WHITE)
        return b

    if view in ('right', 'left'):
        s = 1 if step else -1
        paint(b, ellipse(7 + s, g - 2.2, 1.6, 1.8), GRASS)          # far legs
        paint(b, ellipse(13 - s, g - 2.2, 1.6, 1.8), GRASS)
        skin(2.5, g - 4.5, 1.8, 1.1)                                # tail
        draw_shell(b, 9, g - 13, g - 4, 7, colors, plate_dx=0.5)
        rim(9, g - 4, 7.6, 1.6)
        skin(5 - s, g - 1.8, 1.7, 1.8)                              # near legs
        skin(12 + s, g - 1.8, 1.7, 1.8)
        skin(16, g - 5, 2.2, 1.6)                                   # neck
        skin(17.5, g - 7.5, 3, 2.8)                                 # head
        b.set(18, g - 9, WHITE); b.set(19, g - 9, INK)              # eye
        b.set(18, g - 8, INK); b.set(19, g - 8, INK)
        if angry:
            b.set(17, g - 10, INK); b.set(18, g - 10, INK)          # frown
        else:
            b.set(17, g - 7, PINK)                                  # cheek
        b.set(20, g - 6, GRASS)                                     # mouth
        return b.mirrored() if view == 'left' else b

    if view == 'down' or pose == 'cheer':                           # facing the camera
        draw_shell(b, 11, g - 15, g - 5, 7.5, colors)
        if pose == 'cheer':                                         # hands up!
            skin(3.5, g - 10, 1.8, 2)
            skin(18.5, g - 10, 1.8, 2)
            skin(6.5, g - 1.5, 2, 1.6)
            skin(15.5, g - 1.5, 2, 1.6)
        else:
            skin(4.5, g - 2 - step, 2, 1.8)
            skin(17.5, g - 3 + step, 2, 1.8)
        rim(11, g - 5, 8, 2)
        skin(11, g - 4.5, 3.8, 3.2)                                 # head
        for ex in (8, 12):                                          # eyes
            b.set(ex, g - 6, WHITE); b.set(ex + 1, g - 6, INK)
            b.set(ex, g - 5, INK); b.set(ex + 1, g - 5, INK)
        if angry:
            b.set(8, g - 7, INK); b.set(9, g - 7, INK)
            b.set(12, g - 7, INK); b.set(13, g - 7, INK)
        else:
            b.set(7, g - 4, PINK); b.set(14, g - 4, PINK)
        if pose == 'cheer':
            b.set(10, g - 3, INK); b.set(11, g - 3, INK)
            b.set(10, g - 2, RED_D); b.set(11, g - 2, RED_D)
        else:
            b.set(10, g - 3, GRASS); b.set(11, g - 3, GRASS)
        return b

    # view == 'up': seen from behind
    skin(11, g - 14, 2.6, 2.2)                                      # head behind the shell
    skin(4.5, g - 2 - step, 2, 1.8)
    skin(17.5, g - 3 + step, 2, 1.8)
    draw_shell(b, 11, g - 15, g - 4, 7.8, colors)
    rim(11, g - 4, 8.2, 1.8)
    skin(11, g - 1.5, 1.3, 1.4)                                     # tail
    return b

# ---------------------------------------------------------------------------
# The arena: sand floor, colosseum wall, grass and a cheering crowd
# ---------------------------------------------------------------------------
CROWD_FRAMES = 8
TILE = 24                       # the crowd is redrawn piece by piece in tiles of this size
HUD_BOXES = [(3, 3, 46, 23), (VIEW - 49, 3, 46, 23), (3, VIEW - 26, 46, 23), (VIEW - 49, VIEW - 26, 46, 23)]

def wall_dist(x, y):
    '''Distance from a point (in dots) to the wall seen from above: the top circle swept down by the facade.'''
    dx, dy = x - CX, y - CY
    return math.hypot(dx, dy - min(max(dy, 0), FACE_OUT)) - R_OUT

def facade_row(px, py, radius, rows):
    '''Row index (0 = top) of a wall face below the circle `radius`, or None.'''
    for k in range(1, rows + 1):
        if (math.hypot(px, py - k) < radius) != (math.hypot(px, py) < radius):
            return k - 1
    return None

def arena_color(x, y, rng):
    px, py = x + 0.5 - CX, y + 0.5 - CY
    r = math.hypot(px, py)
    speck = rng.random()

    if abs(py) < 5.5 and R_IN - 0.5 <= r < R_OUT + 0.5:                # east / west gates
        u = r - R_IN
        if abs(py) >= 4.5:
            return INK
        if u < 1.5:                                                     # portcullis
            return STEEL if int(y) % 2 == 0 else INK
        return NAVY if u < 4.5 else PLUM

    if r < R_IN:
        if py < 0 and math.hypot(px, py - FACE_IN) >= R_IN:            # inner wall (north side)
            v = facade_row(px, py, R_IN, FACE_IN) or 0
            if v == 0:
                return STEEL
            if v == FACE_IN - 1:
                return NAVY
            arc = (math.atan2(py - v, px) + math.pi) * R_IN
            return NAVY if (arc + 3 * (v % 2)) % 6 < 1 else SLATE
        fx, fy = px, py - FACE_IN                                       # sand floor
        color = SAND_L if speck < 0.035 else CLAY if speck < 0.06 else SAND
        if abs(math.hypot(fx, fy) - 22) < 0.5 or abs(math.hypot(fx, fy) - 4) < 0.5:
            color = SAND_L                                              # marks in the centre
        shade = 0
        if math.hypot(fx - 2.4, fy - 3.2) > R_IN:                       # shadow of the wall
            shade = 1
        elif math.hypot(fx - 3.6, fy - 4.8) > R_IN and (x + y) % 2 == 0:
            shade = 1
        if py > 0 and r > R_IN - 1.2:
            shade = 1
        if shade:
            color = {SAND_L: SAND, SAND: CLAY, CLAY: SAND_D}[color]
        return color

    if r < R_OUT:                                                       # top of the wall
        u = r - R_IN
        facing = -(0.6 * px + 0.8 * py) / r                             # > 0 : outer edge faces the light
        arc = (math.atan2(py, px) + math.pi) * (R_IN + 3.5)
        color = GRAY
        if 3.3 <= u < 4.3 or (arc + (3.5 if u >= 4 else 0)) % 7 < 1:
            color = STEEL
        elif speck < 0.05:
            color = SILVER
        elif speck < 0.1:
            color = STEEL
        if u >= 6:
            color = SILVER if facing > 0.2 else STEEL if facing < -0.3 else GRAY
        elif u < 1:
            color = SILVER if facing < -0.2 else SLATE if facing > 0.3 else GRAY
        return color

    if py > 0 and wall_dist(x + 0.5, y + 0.5) < 0:                     # colosseum facade (south side)
        v = facade_row(px, py, R_OUT, FACE_OUT)
        v = FACE_OUT - 1 if v is None else v
        p = ((math.atan2(py - v, px) + math.pi) * R_OUT) % 6
        if v == 0:
            return GRAY
        if v == 1:
            return STEEL
        if v == FACE_OUT - 1:
            return SLATE
        if p < 2:                                                       # pillar
            return GRAY if p < 1 else STEEL
        if v == 2:
            return INK if 3 <= p < 5 else STEEL
        return INK if v == 3 else NAVY if v < FACE_OUT - 2 else PLUM

    if abs(py) < 4.5 and abs(px) > R_OUT - 1:                           # dirt road from the gates
        if abs(py) >= 3.5:
            return SAND_D
        return SAND_L if speck < 0.06 else SAND_D if speck < 0.12 else CLAY

    color = GRASS_D if speck < 0.05 else GRASS                          # grass
    if wall_dist(x + 0.5 - 3.0, y + 0.5 - 4.0) < 0 or \
       (wall_dist(x + 0.5 - 4.2, y + 0.5 - 5.6) < 0 and (x + y) % 2 == 0):
        color = TEAL if color == GRASS_D else GRASS_D                   # shadow of the wall
    return color

FAN_POSES = {
    'down':    ['.......', '.......', '..hhh..', '..sss..', '..sss..', '.tTTTt.', '.sTTTs.', '..TTT..', '..p.p..', '..p.p..'],
    'up':      ['.s...s.', '.t...t.', '.thhht.', '..sss..', '..sss..', '..TTT..', '..TTT..', '..TTT..', '..p.p..', '..p.p..'],
    'wave':    ['.s.....', '.t.....', '.thhh..', '..sss..', '..sss..', '..TTTt.', '..TTTs.', '..TTT..', '..p.p..', '..p.p..'],
    'jump':    ['.s...s.', '.t...t.', '.thhht.', '..sss..', '..sss..', '..TTT..', '..TTT..', '..TTT..', '.p...p.', '.......'],
    'slump':   ['.......', '.......', '.......', '..hhh..', '..hhh..', '.tTTTt.', '.sTTTs.', '..TTT..', '..p.p..', '..p.p..'],
    'grief':   ['.......', '.......', '.shhhs.', '.tssst.', '.tssst.', '.tTTTt.', '..TTT..', '..TTT..', '..p.p..', '..p.p..'],
    'clap':    ['.......', '.......', '..hhh..', '..sss..', '..sss..', 'sTTTTTs', '..TTT..', '..TTT..', '..p.p..', '..p.p..'],
    'clapped': ['.......', '.......', '..hhh..', '..sss..', '..sss..', '.tTsTt.', '..TTT..', '..TTT..', '..p.p..', '..p.p..'],
}
FAN_DANCES = [                      # most fans move only now and then, each at its own timing
    ['down', 'down', 'down', 'up', 'jump', 'up', 'down', 'down'],
    ['down', 'down', 'wave', 'down', 'wave', 'down', 'down', 'down'],
    ['down', 'down', 'down', 'down', 'wave!', 'wave!', 'down', 'down'],
    ['down', 'down', 'down', 'down', 'down', 'up', 'down', 'down'],
    ['down'] * 8,
]
CHEER_DANCES = [                    # the fans of the round's winner
    ['up', 'jump', 'up', 'jump', 'up', 'jump', 'up', 'jump'],
    ['jump', 'up', 'down', 'up', 'jump', 'up', 'down', 'up'],
    ['wave', 'wave!', 'wave', 'wave!', 'wave', 'wave!', 'wave', 'wave!'],
    ['up', 'up', 'jump', 'jump', 'up', 'up', 'jump', 'jump'],
]
SAD_DANCES = [                      # the fans of the round's loser: heads down, hands on heads
    ['slump'] * 8,
    ['slump', 'slump', 'slump', 'grief', 'grief', 'grief', 'slump', 'slump'],
    ['grief'] * 8,
    ['down', 'slump', 'slump', 'slump', 'slump', 'slump', 'slump', 'down'],
]
MOODS = ('normal', 'blue', 'red')   # 'blue' / 'red': that color just won a round
SHIRTS = {'blue': [(BLUE, BLUE_D), (CYAN, BLUE), (BLUE_D, NAVY)],
          'red': [(RED, RED_D), (PINK, RED), (ORANGE, RUST)],
          'none': [(WHITE, SILVER), (YELLOW, GOLD), (MAGENTA, PURPLE), (SAND_L, CLAY)]}
HAIRS = [INK, BROWN, PLUM, RUST, GOLD, SILVER, INK, BROWN]
SKINS = [SKIN, SKIN, CLAY, SAND_D, BROWN]

def make_fans(rng):
    '''Scatter the fans at random over all the grass (but not on top of each other).'''
    fans, grid = [], {}
    for _ in range(12000):
        x, y = rng.randrange(2, VIEW - 2), rng.randrange(12, VIEW + 5)
        south = min(max((y - CY) / (R_OUT * 0.5), 0), 1)
        if wall_dist(x, y) < 3 + 7 * south:                             # keep the facade visible
            continue
        if abs(y - CY) < 12 and abs(x - CX) > R_OUT - 4:                # keep the roads clear
            continue
        if abs(x - CX) < 13 and y < CY - R_OUT + 2:                     # the emperor's box
            continue
        gx, gy = x // 6, y // 7
        if any(((x - fx) / 5.5) ** 2 + ((y - fy) / 6.5) ** 2 < 1
               for i in (-1, 0, 1) for j in (-1, 0, 1) for fx, fy in grid.get((gx + i, gy + j), ())):
            continue
        grid.setdefault((gx, gy), []).append((x, y))
        side = 'blue' if rng.random() < min(max(0.5 - (x - CX) / 50, 0.08), 0.92) else 'red'
        team = side if rng.random() < 0.7 else 'none'
        shirt, shade = rng.choice(SHIRTS[team])
        kind = rng.randrange(len(FAN_DANCES))
        fans.append(dict(x=x, y=y, side=side, kind=kind, dance=FAN_DANCES[kind], phase=rng.randrange(CROWD_FRAMES),
                         hair=rng.choice(HAIRS), skin=rng.choice(SKINS), shirt=shirt, shade=shade,
                         pants=rng.choice([NAVY, SLATE, BROWN, PLUM]),
                         flag=(RED if side == 'red' else BLUE) if rng.random() < 0.06 else None))
    fans.sort(key=lambda f: f['y'])
    return fans

def fan_look(fan, mood, frame):
    '''How a fan looks in a frame: (pose, flag position or None).
    After a round the winner's fans cheer and the loser's fans are let down.'''
    step = (frame + fan['phase']) % CROWD_FRAMES
    if mood != 'normal' and mood != fan['side']:
        return SAD_DANCES[fan['kind'] % len(SAD_DANCES)][step], None   # the flag goes down, too
    if fan['flag']:
        if mood == 'normal':
            return 'up', frame // 2 % 2
        return ('jump' if step % 2 else 'up'), frame % 2
    if mood == 'normal':
        return fan['dance'][step], None
    return CHEER_DANCES[fan['kind'] % len(CHEER_DANCES)][step], None

def fan_bitmap(fan, look):
    pose, flag = look
    mirror = pose.endswith('!')
    pose = pose.rstrip('!')
    legend = {'h': fan['hair'], 's': fan['skin'], 'T': fan['shirt'], 't': fan['shade'], 'p': fan['pants']}
    b = Bitmap(13, 17)
    body = sprite(FAN_POSES[pose], legend)
    if mirror:
        body = body.mirrored()
    b.blit(body, 3, 6 if pose == 'jump' else 7)
    if flag is not None:                                                # a waving flag on a pole
        for j in range(5):
            b.set(8, 2 + j, BROWN)
        for j in range(3):
            for i in range(3):
                b.set(9 + i, 2 + j + (1 if i == 1 and flag else 0), fan['flag'] if j < 2 else None)
        b.set(8, 1, GOLD)
    return b.outline(TEAL)

FLAMES = [['.o.', '.go', 'ogo', 'oyo'], ['o..', '.o.', 'ogo', 'gyo'],
          ['.o.', 'og.', 'ogo', 'oyg'], ['..o', '.o.', 'ogo', 'oyo']]
FLAME_COLORS = {'o': ORANGE, 'g': GOLD, 'y': YELLOW}

def draw_torch(b, x, y, frame):
    b.rect(x - 1, y, 3, 1, BROWN)
    b.rect(x - 2, y - 1, 5, 1, INK)
    b.set(x, y + 1, INK)
    b.blit(sprite(FLAMES[frame], FLAME_COLORS).outline(RUST), x - 2, y - 6)

def draw_flag(b, x, y, color, frame):
    for j in range(7):
        b.set(x, y - j, INK)
    b.set(x, y - 7, GOLD)
    for j in range(3):
        for i in range(5):
            b.set(x + 1 + i, y - 6 + j + ((i + frame) % 4 == 0), color if j < 2 else RED_D if color == RED else BLUE_D)

def draw_banner(b, x, y, color, dark):
    b.rect(x - 2, y, 5, 1, GOLD)
    for j in range(1, 6):
        b.set(x - 1, y + j, color)
        b.set(x, y + j, color)
        b.set(x + 1, y + j, dark)
    b.set(x, y + 5, INK)
    b.set(x, y + 3, YELLOW)

ROYAL_BOX = (CX - 11, CY - R_OUT - 20)                  # top-left of the emperor's box (dots)

def royal_box_bitmap(pose='sit', frame=0, flag=None):
    '''The emperor's box: the king sits behind a striped awning. After each round he raises
    the winner's flag (pose 'flag'), and when the game is over he stands up and claps.'''
    legend = {'h': GOLD, 's': SKIN, 'T': PURPLE, 't': PLUM, 'p': PLUM}
    if pose == 'flag':
        body = sprite(FAN_POSES['wave'], legend).mirrored()             # right hand up
    elif pose == 'clap':
        body = sprite(FAN_POSES['clapped' if frame else 'clap'], legend)
    else:
        body = sprite(FAN_POSES['down'], legend)
    king = Bitmap(13, 18)
    king.blit(body, 2, 7)
    king.set(4, 8, GOLD); king.set(6, 8, GOLD); king.set(5, 9, RED)     # crown
    if pose == 'flag':
        color, dark = (RED, RED_D) if flag == 'red' else (BLUE, BLUE_D)
        for j in range(1, 7):
            king.set(7, j, BROWN)
        king.set(7, 0, GOLD)
        for j in range(3):
            for i in range(4):
                king.set(8 + i, 1 + j + ((i + frame) % 2 if i else 0), color if j < 2 else dark)
    king.outline(INK)

    b = Bitmap(22, 26)
    b.blit(king, 4, 3 if pose == 'clap' else 6)                        # he stands up to clap
    for i in range(1, 21):                                              # striped awning
        b.set(i, 20, INK)
    for i in range(2, 20):
        for j in range(21, 25):
            b.set(i, j, MAGENTA if ((i - 2) // 3) % 2 == 0 else PURPLE)
        b.set(i, 25, GOLD if i % 2 == 0 else RUST)
    for j in range(20, 26):
        b.set(1, j, INK); b.set(20, j, INK)
    return b

def build_arena(seed=7):
    '''Draw the arena. Only the crowd, the torches and the flags move, so it is drawn CROWD_FRAMES
    times for every crowd mood. Also returns everything that moves with its box, which is used
    later to find the small parts of the screen that change between two frames.'''
    rng = random.Random(seed)
    base = Bitmap(VIEW, VIEW)
    for y in range(VIEW):
        for x in range(VIEW):
            base.px[y][x] = arena_color(x, y, rng)
    for _ in range(260):                                                # grass tufts and flowers
        x, y = rng.randrange(2, VIEW - 2), rng.randrange(2, VIEW - 2)
        if base.get(x, y) == GRASS and base.get(x, y + 1) == GRASS and base.get(x - 1, y - 1) == GRASS:
            if rng.random() < 0.12:
                base.set(x, y, rng.choice([YELLOW, WHITE, PINK])); base.set(x, y + 1, GRASS_D)
            else:
                base.set(x, y, GRASS_L); base.set(x - 1, y - 1, GRASS_L); base.set(x + 1, y - 1, GRASS_L)
    for _ in range(60):                                                 # pebbles in the sand
        x, y = rng.randrange(VIEW), rng.randrange(VIEW)
        if base.get(x, y) == SAND and base.get(x + 1, y) == SAND:
            base.set(x, y, SAND_D); base.set(x + 1, y, CLAY); base.set(x, y - 1, SAND_L)
    for a, color, dark in ((62, RED, RED_D), (80, RED, RED_D), (100, BLUE, BLUE_D), (118, BLUE, BLUE_D)):
        t = math.radians(a)
        draw_banner(base, round(CX + R_OUT * math.cos(t)), round(CY + R_OUT * math.sin(t)), color, dark)

    fans = make_fans(rng)
    flags = [(CX + side * (R_IN + 4) - (5 if side < 0 else 0), CY + dy, color)
             for side, color in ((1, RED), (-1, BLUE)) for dy in (-7, 8)]
    torches = [(round(CX + (R_IN + 3.5) * math.cos(math.radians(a))),
                round(CY + (R_IN + 3.5) * math.sin(math.radians(a))), a // 90) for a in (45, 135, 225, 315)]
    looks = {}                                                          # each fan is drawn once per look
    frames = {}
    for mood in MOODS:
        frames[mood] = []
        for f in range(CROWD_FRAMES):
            b = base.copy()
            for x, y, color in flags:
                draw_flag(b, x, y, color, f // 2)
            for x, y, k in torches:
                draw_torch(b, x, y, (f + k) % len(FLAMES))
            for i, fan in enumerate(fans):
                look = fan_look(fan, mood, f)
                if (i, look) not in looks:
                    looks[i, look] = fan_bitmap(fan, look)
                b.blit(looks[i, look], fan['x'] - 6, fan['y'] - 16)
            frames[mood].append(b)

    movers = [((x - 1, y - 8, x + 7, y + 2), lambda mood, f: f // 2) for x, y, _ in flags]
    movers += [((x - 3, y - 7, x + 4, y + 2), lambda mood, f: f) for x, y, _ in torches]
    movers += [((fan['x'] - 6, fan['y'] - 16, fan['x'] + 7, fan['y'] + 1),
                lambda mood, f, fan=fan: fan_look(fan, mood, f)) for fan in fans]
    return frames, movers

def changed_pieces(movers, a, b):
    '''Screen rectangles (in pixels) that differ between the arena frames a and b
    (each one is (mood, frame)), merged tile by tile.'''
    tiles = {}
    for (x0, y0, x1, y1), look in movers:
        if look(*a) != look(*b):
            key = ((x0 + x1) // 2 // TILE, (y0 + y1) // 2 // TILE)
            r = tiles.get(key, (x0, y0, x1, y1))
            tiles[key] = (min(r[0], x0), min(r[1], y0), max(r[2], x1), max(r[3], y1))
    return [(max(0, x0) * DOT, max(0, y0) * DOT, min(VIEW, x1) * DOT, min(VIEW, y1) * DOT)
            for x0, y0, x1, y1 in tiles.values()]

# ---------------------------------------------------------------------------
# UI pieces and effects
# ---------------------------------------------------------------------------
GOLD_TEXT = [YELLOW, YELLOW, GOLD, GOLD, ORANGE, ORANGE, RUST]
BLUE_TEXT = [WHITE, CYAN, CYAN, BLUE, BLUE, BLUE_D, BLUE_D]
RED_TEXT = [WHITE, PINK, PINK, RED, RED, RED_D, RED_D]

def big_text(text, colors, scale):
    '''Title style text: gradient letters, a dark outline and a white rim.'''
    b = text_bitmap(text, colors, scale, outline=INK, shadow=PLUM)
    big = Bitmap(b.w + 2, b.h + 2)
    big.blit(b, 1, 1)
    return big.outline(WHITE)

def panel_bitmap(w, h, alpha=''):
    '''A retro RPG style window; alpha (e.g. '99') makes the inside see-through.'''
    b = Bitmap(w, h, INK)
    b.rect(1, 1, w - 2, h - 2, SILVER)
    b.rect(2, h - 2, w - 3, 1, GRAY)
    b.rect(w - 2, 2, 1, h - 3, GRAY)
    b.rect(2, 2, w - 4, h - 4, INK)
    b.rect(3, 3, w - 6, h - 6, NAVY + alpha)
    b.rect(3, 3, w - 6, 1, SLATE + alpha)
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        b.set(x, y, None)
    for x, y in ((1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2)):
        b.set(x, y, INK)
    return b

def button_bitmap(label, hover=False):
    w, h = 66, 17
    face, light, dark = (YELLOW, WHITE, GOLD) if hover else (GOLD, YELLOW, ORANGE)
    b = Bitmap(w, h)
    b.rect(1, 0, w - 2, h, INK)
    b.rect(0, 1, w, h - 2, INK)
    b.rect(1, 1, w - 2, h - 2, face)
    b.rect(2, 1, w - 4, 1, light)
    b.rect(1, h - 5, w - 2, 2, dark)
    b.rect(1, h - 3, w - 2, 2, RUST)
    b.rect(1, h - 2, w - 2, 1, BROWN)
    text = text_bitmap(f'> {label} <' if hover else label, BROWN)
    b.blit(text, (w - text.w) // 2, 3)
    return b

def burst_bitmap(size):
    '''A comic style "POW" burst.'''
    b = Bitmap(2 * size + 3, 2 * size + 3)
    c = size + 1.5
    for y in range(b.h):
        for x in range(b.w):
            dx, dy = x + 0.5 - c, y + 0.5 - c
            r, a = math.hypot(dx, dy), math.atan2(dy, dx)
            edge = size * (0.62 + 0.38 * abs(math.cos(4 * a)) ** 3)
            if r <= edge:
                b.px[y][x] = WHITE if r < edge * 0.45 else YELLOW if r < edge * 0.75 else ORANGE
    return b.outline(RUST).outline(INK)

STAR = ['..y..', '.yyy.', 'yyyyy', '.yyy.', '.y.y.']
HEART = ['.r.r.', 'rRrrr', 'rrrrr', '.rrr.', '..r..']

def star_bitmap():
    return sprite(STAR, {'y': YELLOW}).outline(INK)

def heart_bitmap(full=True):
    colors = {'r': RED, 'R': WHITE} if full else {'r': SLATE, 'R': SLATE}
    return sprite(HEART, colors).outline(INK)

def puff_bitmap(r):
    b = Bitmap(2 * r + 3, 2 * r + 3)
    paint(b, ellipse(r + 1.5, r + 1.5, r, r), lit(r + 1.5, r + 1.5, r, r, WHITE, SAND_L, SAND), line=None)
    return b

def you_bitmap():
    '''A "YOU" tag with an arrow pointing down at the player's turtle.'''
    text = text_bitmap('YOU', INK)
    w = text.w + 6
    b = Bitmap(w, 17)
    b.rect(1, 1, w - 2, 11, YELLOW)
    b.rect(2, 1, w - 4, 1, WHITE)
    b.set(1, 1, None); b.set(w - 2, 1, None); b.set(1, 11, None); b.set(w - 2, 11, None)
    for j, half in enumerate((3, 2, 1, 0)):
        b.rect(w // 2 - half, 12 + j, 2 * half + 1, 1, YELLOW)
    b.blit(text, 3, 3)
    return b.outline(INK)

def chase_bitmap(team, right=True):
    '''A fat arrow in the chaser's colors that points from the chaser to the runner.'''
    light, base, dark = TEAM[team]
    b = Bitmap(20, 13)
    for x in range(2, 12):                          # the shaft
        b.rect(x, 4, 1, 5, base)
        b.set(x, 4, light)
        b.set(x, 8, dark)
    for i in range(6):                              # the head
        b.rect(12 + i, 1 + i, 1, 11 - 2 * i, base)
        b.set(12 + i, 1 + i, light)
        b.set(12 + i, 11 - i, dark)
    b.rect(3, 5, 3, 1, WHITE)
    b.outline(INK)
    return b if right else b.mirrored()

def option_bitmap(label, selected, hover=False, w=50):
    '''A small menu button: gold when it is selected.'''
    h = 13
    face, light, textc = (GOLD, YELLOW, BROWN) if selected else (STEEL, GRAY, WHITE) if hover else (NAVY, SLATE, GRAY)
    b = Bitmap(w, h)
    b.rect(1, 0, w - 2, h, INK)
    b.rect(0, 1, w, h - 2, INK)
    b.rect(1, 1, w - 2, h - 2, face)
    b.rect(2, 1, w - 4, 1, light)
    b.rect(1, h - 2, w - 2, 1, RUST if selected else INK)
    text = text_bitmap(label, textc)
    b.blit(text, (w - text.w) // 2, 3)
    return b


def to_canvas(x, y):
    '''Dot position on the screen -> Tk canvas coordinate.'''
    return x * DOT - SIZE // 2, y * DOT - SIZE // 2

def to_dots(x, y):
    '''Turtle coordinate -> dot position on the screen.'''
    return round((x + SIZE / 2) / DOT), round((SIZE / 2 - y) / DOT)

def snap(v):
    return round(v / DOT) * DOT

class Art:
    '''Converts the pixel art into Tk images once and registers the turtle sprites.'''
    def __init__(self, screen):
        frames, self.movers = build_arena()
        self.arena = {mood: [b.photo() for b in frames[mood]] for mood in MOODS}
        self.pieces = {}
        for team in TEAM:
            for view in ('right', 'left', 'down', 'up'):
                for step in (0, 1):
                    self.add_shape(screen, f'{team}_{view}{step}', turtle_bitmap(team, view, step))
            for hop in range(4):
                self.add_shape(screen, f'{team}_cheer{hop}', turtle_bitmap(team, 'down', hop=hop, pose='cheer'))
            self.add_shape(screen, f'{team}_hide', turtle_bitmap(team, 'down', pose='hide'))
        self.cache = {}

    def add_shape(self, screen, name, bitmap):
        screen.register_shape(name, turtle.Shape('image', bitmap.photo()))

    def picture(self, key, make):
        '''Return (Tk image, width, height in dots); each bitmap is converted only once.'''
        if key not in self.cache:
            bitmap = make()
            self.cache[key] = (bitmap.photo(), bitmap.w, bitmap.h)
        return self.cache[key]

    def crowd_pieces(self, a, b):
        if (a, b) not in self.pieces:
            self.pieces[a, b] = changed_pieces(self.movers, a, b)
        return self.pieces[a, b]

# ---------------------------------------------------------------------------
# Sound: free chiptune music and effects from the 'sounds' folder (CC0, see sounds/CREDITS.txt)
# ---------------------------------------------------------------------------
SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sounds')
SOUNDS = ['music_title', 'music_play', 'music_hurry', 'music_end', 'crowd', 'cheer', 'select', 'click',
          'ready', 'go', 'tick', 'alarm', 'charge', 'catch', 'win', 'lose', 'coin', 'gameover', 'fanfare']

# macOS: one helper process plays all the sounds with AppKit's NSSound; the game sends it
# one line per command ('play', 'loop' or 'stop' + the name). It quits when the game quits.
MAC_PLAYER = r'''
ObjC.import('AppKit');
var sounds = {}, rest = '', input = $.NSFileHandle.fileHandleWithStandardInput;
while (true) {
    var data = input.availableData;
    if (data.length == 0) break;
    rest += $.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding).js;
    var lines = rest.split('\n');
    rest = lines.pop();
    lines.forEach(function (line) {
        var p = line.split('\t'), s = sounds[p[1]];
        if (p[0] == 'load') sounds[p[1]] = $.NSSound.alloc.initWithContentsOfFileByReference(p[2], false);
        else if (s && p[0] == 'stop') s.stop;
        else if (s) { s.stop; s.setLoops(p[0] == 'loop'); s.play; }
    });
}
'''

class Sound:
    '''Background music, crowd noise and sound effects. Python has no sound module that works
    everywhere, so this uses what each system already has: NSSound on macOS, the MCI of
    winmm on Windows and paplay / aplay on Linux. Without them the game just stays silent.'''
    def __init__(self):
        self.on, self.song, self.song_started, self.song_at, self.crowd_on = True, None, False, 0.0, False
        self.send, self.poll, self.quit = None, None, None
        self.files = {name: os.path.join(SOUND_DIR, name + '.wav') for name in SOUNDS}
        if not all(os.path.exists(path) for path in self.files.values()):
            return
        try:
            if sys.platform == 'darwin':
                self.start_mac()
            elif sys.platform == 'win32':
                self.start_windows()
            else:
                self.start_linux()
        except Exception:
            self.send = None

    def start_mac(self):
        helper = subprocess.Popen(['osascript', '-l', 'JavaScript', '-e', MAC_PLAYER], stdin=subprocess.PIPE,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
        def send(command, name):
            helper.stdin.write(f'{command}\t{name}\n')
            helper.stdin.flush()
        for name, path in self.files.items():
            helper.stdin.write(f'load\t{name}\t{path}\n')
        self.send, self.quit = send, lambda: helper.stdin.close()

    def start_windows(self):
        import ctypes
        mci = ctypes.windll.winmm.mciSendStringW
        opened = [mci(f'open "{path}" type mpegvideo alias {name}', None, 0, None) == 0
                  for name, path in self.files.items()]
        if not all(opened):
            mci('close all', None, 0, None)
            return
        mode, loops = ctypes.create_unicode_buffer(32), set()
        def send(command, name):
            loops.discard(name)
            mci(f'stop {name}' if command == 'stop' else f'play {name} from 0', None, 0, None)
            if command == 'loop':
                loops.add(name)
        def poll():                     # start the loops again when they end
            for name in list(loops):
                mci(f'status {name} mode', mode, 32, None)
                if mode.value == 'stopped':
                    mci(f'play {name} from 0', None, 0, None)
        self.send, self.poll, self.quit = send, poll, lambda: mci('close all', None, 0, None)

    def start_linux(self):
        player = shutil.which('paplay') or shutil.which('aplay')
        if not player:
            return
        playing, loops = {}, set()
        def send(command, name):
            old, _ = playing.pop(name, (None, 0))
            if old and old.poll() is None:
                old.terminate()
            loops.discard(name)
            if command != 'stop':
                process = subprocess.Popen([player, self.files[name]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                playing[name] = (process, time.monotonic())
                if command == 'loop':
                    loops.add(name)
        def poll():                     # start the loops again when they end
            for name in list(loops):
                process, started = playing[name]
                if process.poll() is not None:
                    if time.monotonic() - started < 1.0:
                        loops.discard(name)         # it did not play at all: give up
                    else:
                        send('loop', name)
        self.send, self.poll = send, poll
        self.quit = lambda: [send('stop', name) for name in list(playing)]

    def command(self, command, name):
        if self.send:
            try:
                self.send(command, name)
            except Exception:           # the player is gone: go on without sound
                self.close()

    def play(self, name):
        if self.on:
            self.command('play', name)

    def music(self, name, delay=0.0):
        '''Change the background music (None = silence); 'delay' lets a jingle finish first.'''
        if name == self.song:
            return
        if self.song and self.song_started and self.on:
            self.command('stop', self.song)
        self.song, self.song_started, self.song_at = name, False, time.monotonic() + delay
        self.update()

    def crowd(self, on):
        if on != self.crowd_on:
            self.crowd_on = on
            if self.on:
                self.command('loop' if on else 'stop', 'crowd')

    def toggle(self):
        '''M key: sound on / off.'''
        self.on = not self.on
        command = 'loop' if self.on else 'stop'
        if self.song and self.song_started:
            self.command(command, self.song)
        if self.crowd_on:
            self.command(command, 'crowd')

    def update(self):
        if self.song and not self.song_started and time.monotonic() >= self.song_at:
            self.song_started = True
            if self.on:
                self.command('loop', self.song)
        if self.poll:
            self.poll()

    def close(self):
        if self.quit:
            try:
                self.quit()
            except Exception:
                pass
        self.send = None

# ---------------------------------------------------------------------------
# The game
# ---------------------------------------------------------------------------
STAGES = {
    # Runner mode (you run away at 165 px/s): the AI chaser's speed (px/s), turning speed (deg/s),
    # how far ahead of you it aims (s) and its dash attack. It turns slower than you, so dodge
    # sideways when it comes close - in the last 5 seconds it is almost as fast as you.
    'runner': [
        dict(name='ROOKIE',    time=20, speed=105, turn=160, lead=0.1,  dash=False),
        dict(name='GLADIATOR', time=25, speed=121, turn=180, lead=0.15, dash=False),
        dict(name='CHAMPION',  time=30, speed=126, turn=195, lead=0.2,  dash=True),
    ],
    # Chaser mode (you chase): the AI runner's speed, turning speed, how often it rethinks (s),
    # how much it wanders off (deg), and its juke: how close you get before it cuts aside and
    # how fast it goes then. Cut the corners - and in the last 5 seconds you get faster, too.
    'chaser': [
        dict(name='ROOKIE',    time=20, speed=160, turn=300, react=0.3,  wander=40, juke=100, burst=1.4),
        dict(name='GLADIATOR', time=25, speed=168, turn=330, react=0.25, wander=30, juke=110, burst=1.5),
        dict(name='CHAMPION',  time=30, speed=180, turn=360, react=0.18, wander=20, juke=120, burst=1.8),
    ],
}
LIVES = 3
HURRY_TIME, HURRY_BOOST = 5, 1.3    # in the last 5 seconds the chaser runs 30% faster
MENU = [('mode', [('runner', 'RUNNER'), ('chaser', 'CHASER')]),
        ('color', [('blue', 'BLUE'), ('red', 'RED')])]

class RunawayGame:
    def __init__(self, canvas, blue, red, catch_radius=44):
        self.sound = Sound()            # first: the sounds load while the pictures are drawn
        self.canvas = canvas
        self.turtles = {'blue': blue, 'red': red}
        self.catch_radius2 = catch_radius**2
        self.cv = canvas.getcanvas()
        self.art = Art(canvas)

        # What moves the turtles: your keyboard, and an AI for each role
        self.keyboard = ManualMover(canvas)
        self.ai = {'runner': RunawayMover(), 'chaser': ChaseMover()}
        self.mode, self.color, self.menu_row = 'runner', 'blue', 0
        self.assign_roles()

        # Pixel-art arena at the bottom of the canvas, split into small tiles so that
        # redrawing a part of the crowd is cheap
        self.tiles = []
        for ty in range(0, SIZE, TILE * DOT):
            for tx in range(0, SIZE, TILE * DOT):
                photo = tk.PhotoImage(width=TILE * DOT, height=TILE * DOT)
                self.cv.create_image(tx - SIZE // 2, ty - SIZE // 2, image=photo, anchor='nw', tags='bg')
                self.tiles.append((tx, ty, photo))
        self.paint_arena(('normal', 0), (0, 0, SIZE, SIZE))
        self.crowd_clock, self.crowd_frame, self.crowd_speed, self.crowd_queue = 0.0, 0, 5, []
        self.crowd_mood = self.shown_mood = 'normal'

        # The king in the emperor's box
        self.king = self.cv.create_image(*to_canvas(*ROYAL_BOX), anchor='nw', tags='king')
        self.king_look = None
        self.set_king('sit')

        self.items, self.effects = {}, []
        banners = [('READY', GOLD_TEXT, 4), ('GO!', GOLD_TEXT, 4), ('CAUGHT!', RED_TEXT, 4),
                   ('TIME UP!', RED_TEXT, 4), ('STAGE CLEAR!', GOLD_TEXT, 3), ('SPEED UP!', RED_TEXT, 2)]
        for i, stage in enumerate(STAGES['runner']):
            banners += [(f'STAGE {i + 1}', GOLD_TEXT, 4), (f'VS {stage["name"]}', RED_TEXT, 2)]
        for text, colors, scale in banners:             # draw the banners now, so they pop up without a hitch
            self.art.picture(('text', text, tuple(colors), scale, 'big'), lambda: big_text(text, colors, scale))
        self.best = {'runner': 0, 'chaser': 0}
        self.clock, self.shake, self.flash_until = 0.0, 0.0, 0.0
        self.restack()
        self.place_turtles()

        canvas.onkeypress(self.confirm, 'space')
        canvas.onkeypress(self.confirm, 'Return')
        canvas.onkeypress(self.sound.toggle, 'm')
        for key in ('Up', 'Down', 'Left', 'Right', 'w', 's', 'a', 'd'):
            self.cv.bind(f'<KeyPress-{key}>', lambda e, k=key: self.menu_key(k), add='+')
        canvas.listen()

    def assign_roles(self):
        '''Your turtle gets the keyboard, the other turtle gets the AI of the other role.'''
        self.player = self.turtles[self.color]
        self.opponent = self.turtles['red' if self.color == 'blue' else 'blue']
        self.player.brain = self.keyboard
        if self.mode == 'runner':
            self.runner, self.chaser = self.player, self.opponent
            self.opponent.brain = self.ai['chaser']
        else:
            self.runner, self.chaser = self.opponent, self.player
            self.opponent.brain = self.ai['runner']
        self.stages = STAGES[self.mode]

    def place_turtles(self):
        '''Blue starts at the west gate, red at the east gate.'''
        self.turtles['blue'].place(-START_X, START_Y, 'right')
        self.turtles['red'].place(START_X, START_Y, 'left')
        for mover in self.turtles.values():
            mover.pose, mover.boost = None, 1.0

    def is_catched(self):
        p = self.runner.pos()
        q = self.chaser.pos()
        dx, dy = p[0] - q[0], p[1] - q[1]
        return dx**2 + dy**2 < self.catch_radius2

    def start(self, ai_timer_msec=FRAME_MSEC):
        self.ai_timer_msec = ai_timer_msec
        self.last_time = time.monotonic()
        self.enter('title')
        self.canvas.ontimer(self.step, self.ai_timer_msec)

    def step(self):
        start = now = time.monotonic()
        dt = min(now - self.last_time, 0.1)
        self.last_time = now
        self.clock += dt
        self.state_time += dt

        getattr(self, 'update_' + self.state)(dt)
        for mover in self.turtles.values():
            mover.animate(dt)
        self.depth_sort()
        self.update_effects(dt)
        self.update_king()
        self.update_crowd(dt)
        self.update_shake(dt)
        self.sound.update()
        self.canvas.update()

        # Note) The following line should be the last of this function to keep the game playing
        work = int((time.monotonic() - start) * 1000)
        self.canvas.ontimer(self.step, max(1, self.ai_timer_msec - work))

    # -- Scenes ---------------------------------------------------------------
    def enter(self, state):
        self.state, self.state_time = state, 0.0
        self.clear('ui')
        self.hide('you', 'chase')
        self.show_alert(False)
        getattr(self, 'enter_' + state)()

    def confirm(self):
        '''SPACE / ENTER: start from the home screen, or retry with the same settings.'''
        if self.state == 'title' and self.state_time > 0.3:
            self.new_game()
        elif self.state in ('gameover', 'ending') and self.state_time > 1.0:
            self.new_game()

    def new_game(self):
        self.sound.play('click')
        self.sound.music(None)
        self.sound.crowd(True)
        self.assign_roles()
        self.stage, self.lives, self.score = 0, LIVES, 0
        self.show_hud()
        self.enter('intro')

    # Home screen: the turtles walk in, then choose the mode and your turtle
    def enter_title(self):
        self.clear('hud')
        self.clear_effects()
        self.set_mood('normal')
        self.set_king('sit')
        self.place_turtles()
        self.turtles['blue'].place(-MOVE_R, 16, 'right')
        self.turtles['red'].place(MOVE_R, 16, 'left')
        self.crowd_speed = 5
        self.sound.music('music_title')
        self.sound.crowd(False)
        self.show_text('title1', 'TURTLE', 20, GOLD_TEXT, 3, style='big')
        self.show_text('title2', 'RUNAWAY', 47, BLUE_TEXT, 3, style='big')
        self.logo_y = {'title1': 20, 'title2': 47}

    def update_title(self, dt):
        t = self.state_time
        for name, y in self.logo_y.items():          # the logo drops in and bounces
            k = max(0.0, 1 - t / 0.7)
            offset = -90 * k * k if t < 0.7 else -3 * abs(math.sin((t - 0.7) * 9)) * max(0, 1 - (t - 0.7) * 2)
            x, _ = self.cv.coords(self.items[name])
            self.cv.coords(self.items[name], x, to_canvas(0, y + round(offset))[1])
        for mover, target in ((self.turtles['blue'], (-78, 18)), (self.turtles['red'], (78, 18))):
            dx, dy = target[0] - mover.fx, target[1] - mover.fy
            dist = math.hypot(dx, dy)
            if dist > 3:
                mover.move_by(dx / dist * min(dist, 170 * dt), dy / dist * min(dist, 170 * dt))
            else:
                mover.view = 'right' if mover.team == 'blue' else 'left'
                mover.moving = int(t * 3) % 2 == 0   # walking in place, ready to run
        if t > 1.2 and 'start' not in self.items:
            self.show_menu()
        if 'start' in self.items:
            self.show_you(self.turtles[self.color])
            self.show_chase()
            self.cv.itemconfig(self.items['menu_cursor'], state='normal' if int(t * 3) % 2 == 0 else 'hidden')

    def show_menu(self):
        self.show_image('menu', ('panel', 150, 50), lambda: panel_bitmap(150, 50), None, 121)
        self.show_text('menu_mode', 'MODE', 131, GOLD, x=56, style='plain')
        self.show_text('menu_color', 'COLOR', 153, GOLD, x=56, style='plain')
        self.show_button('start', 'START', 176, self.confirm)
        self.show_text('hint', 'ARROWS: SELECT   SPACE: START', 198)
        self.show_text('hint2', 'M: SOUND ON/OFF', 210, GRAY)
        self.refresh_menu()

    def refresh_menu(self):
        for row, (attr, options) in enumerate(MENU):
            for i, (value, label) in enumerate(options):
                selected = getattr(self, attr) == value
                normal = lambda label=label, selected=selected: option_bitmap(label, selected)
                hover = lambda label=label, selected=selected: option_bitmap(label, selected, hover=True)
                self.show_button(f'menu{row}{i}', label, 128 + 22 * row, lambda row=row, value=value: self.choose(row, value),
                                 x=87 + 52 * i, looks=(('option', label, selected, False), normal, ('option', label, selected, True), hover))
        self.show_text('menu_cursor', '>', 131 + 22 * self.menu_row, WHITE, x=49, style='plain')

    def choose(self, row, value):
        self.sound.play('select')
        setattr(self, MENU[row][0], value)
        self.menu_row = row
        self.refresh_menu()

    def menu_key(self, key):
        '''Arrow keys on the home screen: up/down picks a row, left/right changes it.'''
        if self.state != 'title' or 'start' not in self.items:
            return
        if key in ('Up', 'Down', 'w', 's'):
            self.sound.play('select')
            self.menu_row = 1 - self.menu_row
            self.refresh_menu()
        else:
            attr, options = MENU[self.menu_row]
            values = [value for value, _ in options]
            self.choose(self.menu_row, values[1 - values.index(getattr(self, attr))])

    def go_home(self):
        if self.state in ('gameover', 'ending'):
            self.sound.play('click')
            self.enter('title')

    # Stage intro: "STAGE n" -> "READY" -> "GO!"
    def enter_intro(self):
        stage = self.stages[self.stage]
        self.clear_effects()
        self.set_mood('normal')
        self.set_king('sit')
        self.play_time = 0.0
        self.place_turtles()
        self.opponent.brain.configure(stage)
        self.crowd_speed = 8
        self.update_hud()
        self.show_text('stage', f'STAGE {self.stage + 1}', 36, GOLD_TEXT, 4, style='big')
        self.show_text('name', f'VS {stage["name"]}', 73, RED_TEXT, 2, style='big')
        goal = 'SURVIVE' if self.mode == 'runner' else 'CATCH IT IN'
        self.show_text('goal', f'{goal} {stage["time"]} SECONDS!', 95)

    def update_intro(self, dt):
        self.show_you(self.player)
        self.show_chase()
        self.countdown(1.8)

    def countdown(self, delay):
        t = self.state_time
        if t > delay and 'ready' not in self.items:
            self.hide('stage', 'name', 'goal')
            self.show_text('ready', 'READY', 50, GOLD_TEXT, 4, style='big')
            self.sound.play('ready')
        if t > delay + 0.8:
            self.enter('play')
            self.flash('GO!', GOLD_TEXT, 0.6)
            self.sound.play('go')
            hurry = self.stages[self.stage]['time'] - self.play_time <= HURRY_TIME
            self.sound.music('music_hurry' if hurry else 'music_play')

    # After a lost round: back to the start positions
    def enter_ready(self):
        self.clear_effects()
        self.set_mood('normal')
        self.set_king('sit')
        self.place_turtles()
        self.opponent.brain.configure(self.stages[self.stage])
        if self.mode == 'chaser':
            self.play_time = 0.0            # a new try with the full time
        self.update_hud()

    def update_ready(self, dt):
        self.show_you(self.player)
        self.show_chase()
        self.countdown(0.0)

    def enter_play(self):
        self.crowd_speed = 4
        self.remain = None

    def update_play(self, dt):
        stage = self.stages[self.stage]
        if self.flash_until and self.state_time > self.flash_until:
            self.flash_until = 0.0
            self.hide('flash')
        self.runner.run_ai(self.chaser.feet(), self.chaser.heading(), dt)
        self.chaser.run_ai(self.runner.feet(), self.runner.heading(), dt)
        if self.chaser.brain.dashing() and random.random() < 0.5:
            self.add_puff(self.chaser.fx, self.chaser.fy)
        if self.chaser.brain.charging() and 'alert' not in self.items:
            self.sound.play('charge')
        self.show_alert(self.chaser.brain.charging())

        # Hurry up: in the last seconds the chaser gets faster (and the music, too)
        if stage['time'] - self.play_time <= HURRY_TIME and self.chaser.boost == 1.0:
            self.chaser.boost = HURRY_BOOST
            self.flash('SPEED UP!', RED_TEXT, 1.0, y=26, scale=2)
            self.sound.play('alarm')
            self.sound.music('music_hurry')
        if self.chaser.boost > 1.0 and random.random() < 0.25:
            self.add_puff(self.chaser.fx, self.chaser.fy)

        # Scoring (runner mode): +10 points for every second you survive
        before = int(self.play_time)
        self.play_time += dt
        if self.mode == 'runner':
            self.score += 10 * (int(self.play_time) - before)
        self.update_hud()
        remain = math.ceil(stage['time'] - self.play_time)
        if remain != self.remain and 0 < remain < HURRY_TIME:
            self.sound.play('tick')                 # tick, tick, tick...
        self.remain = remain

        if self.is_catched():
            self.round_over(self.chaser)
        elif self.play_time >= stage['time']:
            self.round_over(self.runner)

    def round_over(self, winner):
        '''A round ends with a catch (the chaser wins) or when the time is up (the runner wins).'''
        loser = self.runner if winner is self.chaser else self.chaser
        winner.pose, loser.pose = 'cheer', 'hide'
        self.add_stars(loser)
        self.sound.music(None)
        if winner is self.chaser:
            (x1, y1), (x2, y2) = self.runner.pos(), self.chaser.pos()
            self.add_effect('burst', (x1 + x2) / 2, (y1 + y2) / 2, 0.5)
            self.shake = 0.35
            self.sound.play('catch')
        self.sound.play('win' if winner is self.player else 'lose')
        self.sound.play('cheer')
        self.set_king('flag', winner.team)          # the king raises the winner's flag
        self.set_mood(winner.team)                  # the winner's fans cheer, the others are let down
        self.crowd_speed = 8
        self.enter('clear' if winner is self.player else 'lose')

    # You won the round: bonus points, then the next stage (or the ending)
    def enter_clear(self):
        n = self.stage + 1
        bonuses = [(f'STAGE {n} CLEAR', 300 * n)]                         # harder stages give more
        if self.mode == 'chaser':
            left = max(0, math.ceil(self.stages[self.stage]['time'] - self.play_time))
            bonuses.append((f'TIME LEFT {left}S', 20 * left))             # caught it quickly
        bonuses.append((f'{self.lives} LIVES LEFT' if self.lives > 1 else '1 LIFE LEFT', 100 * self.lives))
        self.bonuses, self.bonus_shown = bonuses, 0
        self.show_text('clear', 'STAGE CLEAR!', 34, GOLD_TEXT, 3, style='big')
        h = 8 + 11 * len(bonuses)
        self.show_image('bonus', ('panel', 132, h, 'clear'), lambda: panel_bitmap(132, h, alpha='80'), None, 64)   # see-through: the turtles stay visible

    def update_clear(self, dt):
        i = self.bonus_shown
        if i < len(self.bonuses) and self.state_time > 0.6 + 0.4 * i:     # the bonuses come in one by one
            name, points = self.bonuses[i]
            self.show_text(f'bonus{i}', f'{name:<13} {"+" + str(points):>5}', 68 + 11 * i, YELLOW, x=62, style='plain')
            self.score += points
            self.update_hud()
            self.sound.play('coin')
            self.bonus_shown += 1
        if self.state_time > 3.0:
            self.stage += 1
            self.enter('ending' if self.stage == len(self.stages) else 'intro')

    # You lost the round: one life less
    def enter_lose(self):
        self.lives -= 1
        self.update_hud()
        top = 140 if (self.runner.fy + self.chaser.fy) / 2 > 0 else 44     # away from the turtles
        self.show_text('lose', 'CAUGHT!' if self.mode == 'runner' else 'TIME UP!', top, RED_TEXT, 4, style='big')
        if self.lives:
            self.show_text('lives', 'LIFE -1', top + 38, WHITE, 2)

    def update_lose(self, dt):
        if self.state_time > 1.8:
            self.enter('gameover' if self.lives <= 0 else 'ready')

    # Closing scene (game over) and ending scene (all stages cleared): the king stands up and claps
    def enter_gameover(self):
        role = 'CHASER' if self.mode == 'runner' else 'RUNNER'
        self.show_result('GAME OVER', RED_TEXT, f'THE {role} WINS...')
        self.sound.crowd(False)
        self.sound.play('gameover')
        self.sound.music('music_end', delay=2.0)            # after the jingle
        self.player.pose, self.opponent.pose = 'hide', 'cheer'
        self.set_king('clap')
        self.set_mood(self.opponent.team)
        self.crowd_speed = 5

    def update_gameover(self, dt):
        self.update_result()

    def enter_ending(self):
        self.show_result('YOU WIN!', GOLD_TEXT, 'ARENA CHAMPION!')
        self.sound.crowd(False)
        self.sound.play('fanfare')
        self.sound.play('cheer')
        self.sound.music('music_end', delay=4.0)
        self.player.pose, self.opponent.pose = 'cheer', 'hide'
        self.add_stars(self.opponent)
        self.set_king('clap')
        self.set_mood(self.player.team)
        self.crowd_speed = 8
        for _ in range(70):
            self.add_confetti()

    def update_ending(self, dt):
        self.update_result()

    def show_result(self, title, colors, subtitle):
        new_best = self.score > self.best[self.mode]
        self.best[self.mode] = max(self.best[self.mode], self.score)
        self.clear('hud')
        self.clear_effects()
        self.turtles['blue'].place(-48, -195, 'down')
        self.turtles['red'].place(48, -195, 'down')
        self.show_image('panel', ('panel', 176, 130), lambda: panel_bitmap(176, 130), None, 36)
        self.show_text('result', title, 46, colors, 3, style='big')
        self.show_text('sub', subtitle, 78, YELLOW)
        self.show_text('score', f'SCORE {self.score:06d}', 92)
        self.show_text('best', f'BEST  {self.best[self.mode]:06d}', 103, WHITE if new_best else GRAY)
        if new_best:
            self.show_text('newbest', 'NEW BEST!', 114, PINK)
        self.show_button('retry', 'RETRY', 126, self.confirm)
        self.show_button('home', 'HOME', 148, self.go_home,
                         looks=(('option', 'HOME', False, False, 40), lambda: option_bitmap('HOME', False, w=40),
                                ('option', 'HOME', False, True, 40), lambda: option_bitmap('HOME', False, True, w=40)))
        self.show_text('hint', 'PRESS SPACE TO RETRY', 192)

    def update_result(self):
        if 'newbest' in self.items:
            self.cv.itemconfig(self.items['newbest'], state='normal' if int(self.state_time * 3) % 2 == 0 else 'hidden')

    # -- HUD --------------------------------------------------------------------
    def show_hud(self):
        for i, (x, y, w, h) in enumerate(HUD_BOXES):
            self.show_image(f'hud{i}', ('panel', w, h), lambda w=w, h=h: panel_bitmap(w, h), x, y, tag='hud')
        for i, label in enumerate(('TIME', 'SCORE', 'LIFE', 'STAGE')):
            x, y, _, _ = HUD_BOXES[i]
            self.show_text(f'label{i}', label, y + 4, GOLD, x=x + 5, tag='hud', style='plain')
        self.hud_values = [None] * 4

    def update_hud(self):
        stage = self.stages[self.stage]
        remain = max(0, math.ceil(stage['time'] - self.play_time))
        warn = remain <= HURRY_TIME and self.state == 'play' and int(self.play_time * 4) % 2 == 0
        values = [(f'{remain:02d}', RED if warn else WHITE), (f'{self.score:06d}', WHITE),
                  (self.lives, 'hearts'), (f'{self.stage + 1}/{len(self.stages)}', WHITE)]
        changed = False
        for i, value in enumerate(values):
            if value == self.hud_values[i]:
                continue
            self.hud_values[i], changed = value, True
            x, y, _, _ = HUD_BOXES[i]
            if value[1] == 'hearts':
                for k in range(LIVES):
                    full = k < self.lives
                    self.show_image(f'heart{k}', ('heart', full), lambda full=full: heart_bitmap(full), x + 4 + 8 * k, y + 12, tag='hud')
            else:
                self.show_text(f'value{i}', value[0], y + 12, value[1], x=x + 5, tag='hud', style='plain')
        if changed:
            self.cv.update_idletasks()              # redraw the HUD corner on its own

    # -- Canvas helpers ---------------------------------------------------------
    def show_image(self, name, key, make, x, y, tag='ui'):
        photo, w, h = self.art.picture(key, make)
        if x is None:
            x = VIEW // 2 - w // 2
        pos = to_canvas(x, y)
        if name in self.items:
            self.cv.itemconfig(self.items[name], image=photo)
            self.cv.coords(self.items[name], *pos)
        else:
            self.items[name] = self.cv.create_image(*pos, image=photo, anchor='nw', tags=(tag,))
            self.restack()
        return self.items[name]

    def show_text(self, name, text, y, color=WHITE, scale=1, x=None, tag='ui', style='outline'):
        colors = tuple(color) if isinstance(color, list) else color
        if style == 'big':
            make = lambda: big_text(text, list(colors), scale)
        elif style == 'plain':
            make = lambda: text_bitmap(text, color, scale, shadow=INK)
        else:
            make = lambda: text_bitmap(text, color, scale, outline=INK)
        return self.show_image(name, ('text', text, colors, scale, style), make, x, y, tag)

    def show_button(self, name, label, y, action, x=None, looks=None):
        '''A clickable button that lights up under the mouse.'''
        if looks is None:
            looks = (('button', label, False), lambda: button_bitmap(label),
                     ('button', label, True), lambda: button_bitmap(label, True))
        item = self.show_image(name, looks[0], looks[1], x, y)
        normal = self.art.picture(looks[0], looks[1])[0]
        hover = self.art.picture(looks[2], looks[3])[0]
        self.cv.tag_bind(item, '<Enter>', lambda e: self.cv.itemconfig(item, image=hover) or self.cv.config(cursor='hand2'))
        self.cv.tag_bind(item, '<Leave>', lambda e: self.cv.itemconfig(item, image=normal) or self.cv.config(cursor=''))
        self.cv.tag_bind(item, '<Button-1>', lambda e: action())

    def show_you(self, mover):
        '''A floating "YOU" arrow above your turtle (only while getting ready).'''
        photo, w, h = self.art.picture(('you',), you_bitmap)
        x, y = to_dots(*mover.pos())
        bob = round(1.5 * math.sin(self.clock * 6))
        self.show_image('you', ('you',), you_bitmap, x - w // 2, y - 7 - h + bob, tag='fx')   # under all text

    def show_chase(self):
        '''An arrow between the turtles, from the chaser to the runner: in runner mode it
        points at you, in chaser mode at the other turtle (only while getting ready).'''
        me = self.turtles[self.color]
        other = self.turtles['red' if self.color == 'blue' else 'blue']
        chaser, runner = (other, me) if self.mode == 'runner' else (me, other)
        (x1, y1), (x2, y2) = to_dots(*chaser.pos()), to_dots(*runner.pos())
        right = x2 > x1
        key = ('chase', chaser.team, right)
        _, w, h = self.art.picture(key, lambda: chase_bitmap(chaser.team, right))
        nudge = round(2 * abs(math.sin(self.clock * 4))) * (1 if right else -1)    # nudging toward the runner
        self.show_image('chase', key, lambda: chase_bitmap(chaser.team, right),
                        (x1 + x2) // 2 - w // 2 + nudge, (y1 + y2) // 2 - h // 2 + 2, tag='fx')

    def flash(self, text, colors, duration, y=50, scale=4):
        self.show_text('flash', text, y, colors, scale, style='big')
        self.flash_until = self.state_time + duration

    def hide(self, *names):
        for name in names:
            if name in self.items:
                self.cv.delete(self.items.pop(name))

    def clear(self, tag):
        for name, item in list(self.items.items()):
            if tag in self.cv.gettags(item):
                self.cv.delete(item)
                del self.items[name]
        if tag == 'ui':
            self.cv.config(cursor='')

    def restack(self):
        '''Keep the layers in order: arena < dust < king < turtles < effects < HUD < UI < confetti.'''
        self.cv.tag_lower('king')
        self.cv.tag_lower('low')
        self.cv.tag_lower('bg')
        for tag in ('fx', 'hud', 'ui', 'confetti'):
            self.cv.tag_raise(tag)

    def depth_sort(self):
        '''The turtle closer to the bottom of the screen is drawn in front.'''
        back, front = sorted(self.turtles.values(), key=lambda m: -m.fy)
        self.cv.tag_lower(back.item(), front.item())

    # -- The king, the crowd, effects and screen shake ------------------------
    def set_king(self, pose, flag=None):
        self.king_pose, self.king_flag = pose, flag

    def update_king(self):
        frame = int(self.clock * 5) % 2 if self.king_pose != 'sit' else 0
        look = (self.king_pose, frame, self.king_flag)
        if look != self.king_look:
            self.king_look = look
            photo = self.art.picture(('king',) + look, lambda: royal_box_bitmap(*look))[0]
            self.cv.itemconfig(self.king, image=photo)
            self.cv.update_idletasks()              # redraw the royal box on its own

    def set_mood(self, mood):
        self.crowd_mood = mood

    def update_crowd(self, dt):
        '''Animate the crowd. A full-screen redraw is slow (it makes the turtles stutter),
        so only small pieces of the crowd are copied at a time, and each is redrawn on its own.'''
        self.crowd_clock += dt * self.crowd_speed
        frame = int(self.crowd_clock) % CROWD_FRAMES
        while self.crowd_frame != frame or self.shown_mood != self.crowd_mood:
            before = (self.shown_mood, self.crowd_frame)
            if self.crowd_frame != frame:
                self.crowd_frame = (self.crowd_frame + 1) % CROWD_FRAMES
            self.shown_mood = self.crowd_mood
            after = (self.shown_mood, self.crowd_frame)
            pieces = [(after, rect) for rect in self.art.crowd_pieces(before, after)]
            random.shuffle(pieces)                  # random order: the fans do not move in sync
            self.crowd_queue += pieces
        if self.crowd_queue:                        # spread the pieces until the next crowd frame
            time_left = (1 - self.crowd_clock % 1) / self.crowd_speed
            count = math.ceil(len(self.crowd_queue) * dt / max(time_left, dt))
            for key, rect in self.crowd_queue[:count]:
                self.paint_arena(key, rect)
                self.cv.update_idletasks()          # redraw this piece on its own
            del self.crowd_queue[:count]

    def paint_arena(self, key, rect):
        '''Copy a rectangle (in screen pixels) of an arena frame onto the background tiles.'''
        x0, y0, x1, y1 = rect
        mood, frame = key
        source = self.art.arena[mood][frame]
        for tx, ty, photo in self.tiles:
            ax, ay = max(x0, tx), max(y0, ty)
            bx, by = min(x1, tx + TILE * DOT), min(y1, ty + TILE * DOT)
            if ax < bx and ay < by:
                photo.tk.call(photo, 'copy', source, '-from', ax, ay, bx, by, '-to', ax - tx, ay - ty)

    def update_shake(self, dt):
        if self.shake > 0:
            self.shake -= dt
            dx, dy = (random.choice((-2, 2)) * DOT, random.choice((-1, 1)) * DOT) if self.shake > 0 else (0, 0)
            half = SIZE // 2
            self.cv.config(scrollregion=(-half + dx, -half + dy, half + dx, half + dy))

    def add_effect(self, kind, x, y, life, **extra):
        if kind == 'burst':
            photo = self.art.picture(('burst', 7), lambda: burst_bitmap(7))[0]
        elif kind == 'star':
            photo = self.art.picture(('star',), star_bitmap)[0]
        else:
            photo = self.art.picture(('puff', extra['size']), lambda: puff_bitmap(extra['size']))[0]
        item = self.cv.create_image(snap(x), -snap(y), image=photo, tags=('low' if kind == 'puff' else 'fx',))
        self.effects.append(dict(kind=kind, item=item, x=x, y=y, age=0.0, life=life, **extra))
        self.restack()

    def show_alert(self, on):
        '''A "!" above the champion while it charges up for a dash.'''
        if on:
            x, y = to_dots(*self.chaser.pos())
            self.show_image('alert', ('alert',), lambda: text_bitmap('!', [WHITE, YELLOW, YELLOW, GOLD, GOLD, ORANGE, ORANGE], 2, outline=INK),
                            x - 6, y - 26, tag='fx')
        else:
            self.hide('alert')

    def add_stars(self, mover):
        for i in range(3):
            self.add_effect('star', 0, 0, 1e9, owner=mover, angle=i * 2 * math.pi / 3)

    def add_puff(self, x, y):
        self.add_effect('puff', x + random.uniform(-12, 12), y + random.uniform(-4, 4), 0.35, size=3)

    def add_confetti(self):
        color = random.choice([RED, BLUE, YELLOW, GRASS_L, PINK, CYAN, WHITE, ORANGE])
        w = random.choice((2, 3))
        item = self.cv.create_rectangle(0, 0, w * DOT, 2 * DOT, fill=color, width=0, tags=('confetti',))
        self.effects.append(dict(kind='confetti', item=item, x=random.uniform(-360, 360), y=random.uniform(-300, 800),
                                 age=0.0, life=1e9, speed=random.uniform(60, 140), phase=random.uniform(0, 6), w=w))
        self.restack()

    def update_effects(self, dt):
        self.confetti_turn = not getattr(self, 'confetti_turn', False)
        for e in self.effects[:]:
            e['age'] += dt
            if e['age'] > e['life']:
                self.cv.delete(e['item'])
                self.effects.remove(e)
                continue
            if e['kind'] == 'burst' and e['age'] > 0.06:
                self.cv.itemconfig(e['item'], image=self.art.picture(('burst', 12), lambda: burst_bitmap(12))[0])
            elif e['kind'] == 'star':               # dizzy stars circle above the head
                a = e['angle'] + e['age'] * 5
                x, y = e['owner'].pos()
                self.cv.coords(e['item'], snap(x + 26 * math.cos(a)), -snap(y + 40 + 8 * math.sin(a)))
            elif e['kind'] == 'puff':
                e['y'] += 20 * dt
                self.cv.coords(e['item'], snap(e['x']), -snap(e['y']))
            elif e['kind'] == 'confetti' and self.confetti_turn:
                e['y'] -= e['speed'] * dt * 2
                if e['y'] < -380:
                    e['y'] = 380
                x = e['x'] + 14 * math.sin(e['age'] * 3 + e['phase'])
                self.cv.coords(e['item'], snap(x), -snap(e['y']), snap(x) + e['w'] * DOT, -snap(e['y']) + 2 * DOT)

    def clear_effects(self):
        for e in self.effects:
            self.cv.delete(e['item'])
        self.effects = []

# ---------------------------------------------------------------------------
# Turtles and what moves them
# ---------------------------------------------------------------------------
class ArenaTurtle(turtle.RawTurtle):
    '''A turtle drawn as a pixel-art sprite; it walks on the sand and cannot leave the arena.
    Its color belongs to the turtle itself, so it never switches when the roles change.
    What moves it (your keyboard or an AI) is its 'brain'.'''
    VIEWS = {'right': 0, 'up': 90, 'left': 180, 'down': 270}

    def __init__(self, canvas, team):
        super().__init__(canvas)
        self.team = team
        self.penup()
        self.speed(0)
        self.setundobuffer(None)
        self.brain, self.boost = None, 1.0
        self.fx = self.fy = 0.0         # position of the feet on the sand
        self.view, self.pose = 'down', None
        self.moving, self.walk_time, self.pose_time = False, 0.0, 0.0

    def run_ai(self, opp_pos, opp_heading, dt):
        self.brain.run_ai(self, opp_pos, opp_heading, dt)

    def place(self, x, y, view):
        self.fx, self.fy, self.view = x, y, view
        self.setheading(self.VIEWS[view])
        self.animate(0)

    def feet(self):
        return self.fx, self.fy

    def move_by(self, dx, dy):
        x, y = self.fx + dx, self.fy + dy
        d = math.hypot(x, y)
        if d > MOVE_R:                  # the round arena wall stops the turtle
            x, y = x * MOVE_R / d, y * MOVE_R / d
        self.fx, self.fy = x, y
        if dx or dy:
            self.setheading(math.degrees(math.atan2(dy, dx)))
            if abs(dx) >= abs(dy) * 0.8:
                self.view = 'right' if dx > 0 else 'left'
            else:
                self.view = 'up' if dy > 0 else 'down'
            self.moving = True

    def item(self):
        return self.turtle._item

    def animate(self, dt):
        '''Pick the sprite for this frame and put it on the dot grid.'''
        self.pose_time = self.pose_time + dt if self.pose else 0.0
        wobble = 0
        if self.pose == 'cheer':
            name = f'{self.team}_cheer{(0, 2, 3, 2)[int(self.pose_time / 0.09) % 4]}'
        elif self.pose == 'hide':
            name = f'{self.team}_hide'
            if self.pose_time < 0.6:
                wobble = DOT if int(self.pose_time / 0.06) % 2 else -DOT
        else:
            if self.moving:
                self.walk_time += dt
            name = f'{self.team}_{self.view}{int(self.walk_time / 0.12) % 2 if self.moving else 0}'
        self.moving = False
        self.shape(name)
        self.setpos(snap(self.fx) + wobble, snap(self.fy) + FOOT)

class Brain:
    '''What moves a turtle: your keyboard (ManualMover) or an AI (ChaseMover, RunawayMover).'''
    def configure(self, stage):
        pass

    def charging(self):
        return False

    def dashing(self):
        return False

class ManualMover(Brain):
    '''You: run with the arrow keys (or WASD).'''
    KEYS = {'Up': (0, 1), 'Down': (0, -1), 'Left': (-1, 0), 'Right': (1, 0),
            'w': (0, 1), 's': (0, -1), 'a': (-1, 0), 'd': (1, 0)}

    def __init__(self, canvas, step_move=165):
        self.step_move = step_move      # pixels per second
        self.pressed = set()

        # Register event handlers
        for key in self.KEYS:
            canvas.onkeypress(lambda k=key: self.pressed.add(k), key)
            canvas.onkeyrelease(lambda k=key: self.pressed.discard(k), key)
        canvas.getcanvas().bind('<FocusOut>', lambda e: self.pressed.clear(), add='+')
        canvas.listen()

    def run_ai(self, me, opp_pos, opp_heading, dt):
        dx = sum(self.KEYS[k][0] for k in self.pressed)
        dy = sum(self.KEYS[k][1] for k in self.pressed)
        if dx or dy:
            step = self.step_move * me.boost * dt / math.hypot(dx, dy)
            me.move_by(dx * step, dy * step)

class ChaseMover(Brain):
    '''The intelligent chaser: it aims where the runner is going and turns smoothly.
    The champion can also charge up ('!') and dash straight at the runner.'''
    def configure(self, stage):
        self.step_move, self.step_turn = stage['speed'], stage['turn']
        self.lead, self.can_dash = stage['lead'], stage['dash']
        self.last_opp, self.opp_vel = None, (0.0, 0.0)
        self.charge_time, self.dash_time, self.dash_wait = 0.0, 0.0, 2.0

    def charging(self):
        return self.charge_time > 0

    def dashing(self):
        return self.dash_time > 0

    def run_ai(self, me, opp_pos, opp_heading, dt):
        ox, oy = opp_pos
        if self.last_opp and dt > 0:    # estimate the runner's velocity
            vx, vy = (ox - self.last_opp[0]) / dt, (oy - self.last_opp[1]) / dt
            k = min(1.0, dt * 6)
            self.opp_vel = (self.opp_vel[0] + (vx - self.opp_vel[0]) * k, self.opp_vel[1] + (vy - self.opp_vel[1]) * k)
        self.last_opp = (ox, oy)

        # Aim ahead of the runner (less when it is already close), inside the arena
        dist = math.hypot(ox - me.fx, oy - me.fy)
        lead = self.lead * min(1.0, dist / 150)
        tx, ty = ox + self.opp_vel[0] * lead, oy + self.opp_vel[1] * lead
        d = math.hypot(tx, ty)
        if d > MOVE_R:
            tx, ty = tx * MOVE_R / d, ty * MOVE_R / d

        # Turn toward the target, but not more than 'step_turn' degrees per second
        want = math.degrees(math.atan2(ty - me.fy, tx - me.fx))
        diff = (want - me.heading() + 180) % 360 - 180
        turn = self.step_turn * dt * (0 if self.dashing() else 2 if self.charging() else 1)
        me.setheading(me.heading() + max(-turn, min(diff, turn)))

        # Dash attack: stop and charge for a moment, then rush straight ahead
        speed = self.step_move * me.boost
        if self.can_dash:
            self.dash_wait -= dt
            if self.charge_time > 0:
                self.charge_time -= dt
                speed = 0
                if self.charge_time <= 0:
                    self.dash_time = 0.35
            elif self.dash_time > 0:
                self.dash_time -= dt
                speed *= 2.3
            elif self.dash_wait <= 0 and dist < 170:
                self.charge_time, self.dash_wait = 0.35, 3.5
        if speed > 0:
            heading = me.heading()
            h = math.radians(heading)
            me.move_by(math.cos(h) * speed * dt, math.sin(h) * speed * dt)
            me.setheading(heading)

class RunawayMover(Brain):
    '''The intelligent runner: it runs away from the chaser and, near the wall, runs along it
    instead of getting stuck. When the chaser comes close it jukes: it cuts aside toward the
    open middle with a burst of speed. It only rethinks now and then and wanders a little,
    so you can cut the corner and catch it.'''
    def configure(self, stage):
        self.step_move, self.step_turn = stage['speed'], stage['turn']
        self.react, self.wander = stage['react'], stage['wander']
        self.juke, self.burst = stage['juke'], stage['burst']
        self.target, self.think = None, 0.0
        self.dodge_time, self.dodge_wait = 0.0, 0.0

    def run_ai(self, me, opp_pos, opp_heading, dt):
        ox, oy = opp_pos
        dist = math.hypot(me.fx - ox, me.fy - oy) or 1.0
        speed = self.step_move * me.boost
        self.think -= dt
        self.dodge_wait -= dt
        if self.dodge_time > 0:                     # in the middle of a juke
            self.dodge_time -= dt
            speed *= self.burst
        elif self.dodge_wait <= 0 and dist < self.juke:
            # Juke: cut aside (toward the middle of the arena) when the chaser comes close
            side = math.degrees(math.atan2(me.fy - oy, me.fx - ox))
            to_middle = math.degrees(math.atan2(-me.fy, -me.fx))
            self.target = max((side + 90, side - 90), key=lambda a: math.cos(math.radians(a - to_middle)))
            me.setheading(self.target)
            self.dodge_time, self.dodge_wait = 0.35, 1.2
        elif self.think <= 0:                       # now and then: where to run?
            self.think = self.react
            ax, ay = (me.fx - ox) / dist, (me.fy - oy) / dist           # away from the chaser
            r = math.hypot(me.fx, me.fy) or 1.0
            nx, ny = me.fx / r, me.fy / r                               # toward the wall
            tx, ty = -ny, nx                                            # along the wall...
            if math.hypot(ox, oy) > 40:                                 # ...going round away from the chaser
                away_round = math.sin(math.atan2(me.fy, me.fx) - math.atan2(oy, ox)) > 0
            else:
                away_round = tx * ax + ty * ay > 0
            if not away_round:
                tx, ty = -tx, -ty
            edge = min(1.0, max(0.0, (r - 0.55 * MOVE_R) / (0.35 * MOVE_R)))
            wx = ax * (1 - edge) + (tx - 0.3 * nx) * edge
            wy = ay * (1 - edge) + (ty - 0.3 * ny) * edge
            self.target = math.degrees(math.atan2(wy, wx)) + random.uniform(-self.wander, self.wander)

        if self.target is not None:
            diff = (self.target - me.heading() + 180) % 360 - 180
            turn = self.step_turn * dt
            me.setheading(me.heading() + max(-turn, min(diff, turn)))
        heading = me.heading()
        h = math.radians(heading)
        me.move_by(math.cos(h) * speed * dt, math.sin(h) * speed * dt)
        me.setheading(heading)

if __name__ == '__main__':
    # Use 'TurtleScreen' instead of 'Screen' to prevent an exception from the singleton 'Screen'
    root = tk.Tk()
    root.title('Turtle Runaway')
    root.resizable(False, False)
    canvas = tk.Canvas(root, width=SIZE, height=SIZE, highlightthickness=0, bg=GRASS)
    canvas.pack()
    screen = turtle.TurtleScreen(canvas)
    screen.tracer(0)                    # draw only when the game calls update()
    screen.bgcolor(TEAL)

    blue = ArenaTurtle(screen, 'blue')
    red = ArenaTurtle(screen, 'red')

    # Choose the mode (runner / chaser) and your turtle on the home screen
    game = RunawayGame(screen, blue, red)
    game.start()
    screen.mainloop()
    game.sound.close()
