from OpenGL.GL import *
import random, numpy, cmath, math, pygame

import ui, globals, drawing, os, copy
from globals.types import Point
import modes
import random
import actors


class Viewpos(object):
    follow_threshold = 0
    max_away = Point(100, 20)
    shake_radius = 10

    def __init__(self, point):
        self._pos = point
        self.NoTarget()
        self.follow = None
        self.follow_locked = False
        self.t = 0
        self.shake_end = None
        self.shake_duration = 1
        self.shake = Point(0, 0)
        self.last_update = globals.time

    def NoTarget(self):
        self.target = None
        self.target_change = None
        self.start_point = None
        self.target_time = None
        self.start_time = None

    @property
    def pos(self):
        return self._pos + self.shake

    def Set(self, point):
        self._pos = point.to_int()
        self.NoTarget()

    def ScreenShake(self, duration):
        self.shake_end = globals.time + duration
        self.shake_duration = float(duration)

    def SetTarget(self, point, t, rate=2, callback=None):
        # Don't fuck with the view if the player is trying to control it
        rate /= 4.0
        self.follow = None
        self.follow_start = 0
        self.follow_locked = False
        self.target = point.to_int()
        self.target_change = self.target - self._pos
        self.start_point = self._pos
        self.start_time = t
        self.duration = self.target_change.length() / rate
        self.callback = callback
        if self.duration < 200:
            self.duration = 200
        self.target_time = self.start_time + self.duration

    def Follow(self, t, actor):
        """
        Follow the given actor around.
        """
        self.follow = actor
        self.follow_start = t
        self.follow_locked = False

    def HasTarget(self):
        return self.target is not None

    def Skip(self):
        self._pos = self.target
        self.NoTarget()
        if self.callback:
            self.callback(self.t)
            self.callback = None

    def Update(self, t):
        try:
            return self.update(t)
        finally:
            self._pos = self._pos.to_int()

    def update(self, t):
        self.t = t
        elapsed = t - self.last_update
        self.last_update = t

        if self.shake_end:
            if t >= self.shake_end:
                self.shake_end = None
                self.shake = Point(0, 0)
            else:
                left = (self.shake_end - t) / self.shake_duration
                radius = left * self.shake_radius
                self.shake = Point(random.random() * radius, random.random() * radius)

        if self.follow:
            # We haven't locked onto it yet, so move closer, and lock on if it's below the threshold
            fpos = (self.follow.GetPosCentre() * globals.tile_dimensions).to_int() + globals.screen * Point(
                0, 0.03
            )
            if not fpos:
                return
            target = fpos - (globals.screen * Point(0.35, 0.46)).to_int()
            diff = target - self._pos
            direction = diff.direction()

            if abs(diff.x) < self.max_away.x and abs(diff.y) < self.max_away.y:
                adjust = diff * 0.02 * elapsed * 0.06
            else:
                adjust = diff * 0.03 * elapsed * 0.06
            # adjust = adjust.to_int()
            if adjust.x == 0 and adjust.y == 0:
                adjust = direction
            self._pos += adjust
            return

        elif self.target:
            if t >= self.target_time:
                self._pos = self.target
                self.NoTarget()
                if self.callback:
                    self.callback(t)
                    self.callback = None
            elif t < self.start_time:  # I don't think we should get this
                return
            else:
                partial = float(t - self.start_time) / self.duration
                partial = partial * partial * (3 - 2 * partial)  # smoothstep
                self._pos = (self.start_point + (self.target_change * partial)).to_int()


class TileTypes:
    SNOW = 1
    WALL = 2
    TILE = 3
    ACTIVATING_ROBOT = 4
    BASHING_ROBOT = 5
    LIGHT = 6
    ROCK = 7
    ENEMY = 8
    TREE = 9
    DOOR_CLOSED = 10
    DOOR_OPEN = 11
    ICE = 12
    CANDY_CANE = 13
    UP_ROCK = 14
    ICE_RIGHT = 15
    ICE_LEFT = 16
    ICE_BOTTOM = 17
    ICE_TOP = 18
    ICE_TOP_RIGHT = 19
    ICE_TOP_LEFT = 20
    ICE_BOTTOM_LEFT = 21
    ICE_BOTTOM_RIGHT = 22
    ROCK_END_RIGHT = 23
    ROCK_END_LEFT = 24

    Impassable = set((WALL, TREE, DOOR_CLOSED, ROCK, CANDY_CANE))
    Doors = set([DOOR_CLOSED, DOOR_OPEN])
    Robots = set([ACTIVATING_ROBOT, BASHING_ROBOT])
    Rocks = set([ROCK, UP_ROCK, ROCK_END_RIGHT, ROCK_END_LEFT])
    Choppable = set([TREE, CANDY_CANE])


class TileData(object):
    texture_names = {
        TileTypes.SNOW: "snow.png",
        TileTypes.WALL: "wall.png",
        TileTypes.TILE: "tile.png",
        TileTypes.TREE: "tree.png",
        TileTypes.ICE: "ice.png",
        TileTypes.ICE_RIGHT: "ice_right.png",
        TileTypes.ICE_LEFT: "ice_left.png",
        TileTypes.ICE_TOP: "ice_top.png",
        TileTypes.ICE_BOTTOM: "ice_bottom.png",
        TileTypes.ICE_TOP_RIGHT: "ice_top_right.png",
        TileTypes.ICE_TOP_LEFT: "ice_top_left.png",
        TileTypes.ICE_BOTTOM_LEFT: "ice_bottom_left.png",
        TileTypes.ICE_BOTTOM_RIGHT: "ice_bottom_right.png",
        TileTypes.ROCK: "rock.png",
        TileTypes.UP_ROCK: "uprock.png",
        TileTypes.CANDY_CANE: "candy_cane.png",
        TileTypes.DOOR_CLOSED: "door_closed.png",
        TileTypes.ROCK_END_RIGHT: "rock_end_right.png",
        TileTypes.ROCK_END_LEFT: "rock_end_left.png",
        TileTypes.DOOR_OPEN: "door_open.png",
    }
    level = 0

    def __init__(self, type, pos, last_type, parent):
        self.pos = pos
        self.type = type
        self.actors = {}
        try:
            self.name = self.texture_names[type]
        except KeyError:
            self.name = self.texture_names[TileTypes.SNOW]
        # Shitty hack
        if self.name == "tree.png":
            self.name = "tree_%d.png" % random.randint(0, 7)
        # How big are we?
        self.size = (globals.atlas.TextureSubimage(self.name).size) / globals.tile_dimensions
        self.mid_point = self.pos + (self.size / 2)
        self.size = self.size.to_int()
        self.quad = drawing.Quad(globals.quad_buffer, tc=globals.atlas.TextureSpriteCoords(self.name))
        bl = pos * globals.tile_dimensions
        tr = bl + self.size * globals.tile_dimensions
        self.quad.SetVertices(bl, tr, self.level)

    def Delete(self):
        self.quad.Delete()

    def Interact(self, robot):
        pass

    def deactivate(self):
        pass

    def Update(self, t):
        pass

    def AddActor(self, actor):
        self.actors[actor] = True

    def Interacted(self):
        pass

    def RemoveActor(self, actor):
        try:
            del self.actors[actor]
        except KeyError:
            pass


class Door(TileData):
    def Toggle(self):
        if self.type == TileTypes.DOOR_CLOSED:
            self.type = TileTypes.DOOR_OPEN
            globals.sounds.door_open.play()
        else:
            self.type = TileTypes.DOOR_CLOSED
            globals.sounds.door_close.play()
        self.quad.SetTextureCoordinates(globals.atlas.TextureSpriteCoords(self.texture_names[self.type]))

    def Interact(self, player):
        self.Toggle()


class LightTile(TileData):
    def __init__(self, type, pos, last_type, parent):
        # Firstly decide what kind of tile we want
        super(LightTile, self).__init__(last_type, pos, last_type, parent)
        self.light = actors.Light(pos)


class TreeTile(TileData):
    level = 1
    base_tile = TileTypes.SNOW

    def __init__(self, type, pos, last_type, parent):
        super(TreeTile, self).__init__(type, pos, last_type, parent)
        self.base = []
        for x in xrange(self.size.x):
            for y in xrange(self.size.y):
                self.base.append(TileData(self.base_tile, pos + Point(x, y), last_type, parent))

    def chop_down(self):
        self.type = self.base_tile
        self.quad.SetTextureCoordinates(globals.atlas.TextureSpriteCoords(self.texture_names[self.type]))


class RockTile(TreeTile):
    def chop_down(self):
        return


class CaneTile(TreeTile):
    base_tile = TileTypes.TILE

    def chop_down(self):
        self.win()

    def Interact(self, other):
        self.win()

    def win(self):
        globals.sounds.chop.stop()
        globals.sounds.robot_dance.play()
        globals.current_view.mode = modes.GameWin(globals.current_view)


def TileDataFactory(map, type, pos, last_type, parent):
    # Why don't I just use a dictionary for this?

    if type in TileTypes.Doors:
        return Door(type, pos, last_type, parent)

    elif type == TileTypes.LIGHT:
        return LightTile(type, pos, last_type, parent)

    elif type == TileTypes.CANDY_CANE:
        map.candy = CaneTile(type, pos, last_type, parent)
        return map.candy

    elif type == TileTypes.TREE:
        return TreeTile(type, pos, last_type, parent)

    elif type in TileTypes.Rocks:
        return RockTile(type, pos, last_type, parent)

    elif type in TileTypes.Robots:
        return TileData(last_type, pos, last_type, parent)
    return TileData(type, pos, last_type, parent)


class GameMap(object):
    input_mapping = {
        " ": TileTypes.SNOW,
        ".": TileTypes.TILE,
        "|": TileTypes.WALL,
        "-": TileTypes.WALL,
        "+": TileTypes.WALL,
        "R": TileTypes.ACTIVATING_ROBOT,
        "r": TileTypes.BASHING_ROBOT,
        "d": TileTypes.DOOR_CLOSED,
        "l": TileTypes.LIGHT,
        "e": TileTypes.ENEMY,
        "T": TileTypes.TREE,
        "i": TileTypes.ICE,
        "b": TileTypes.ROCK,
        "c": TileTypes.CANDY_CANE,
        "B": TileTypes.UP_ROCK,
        "1": TileTypes.ICE_RIGHT,
        "2": TileTypes.ICE_LEFT,
        "3": TileTypes.ICE_TOP,
        "4": TileTypes.ICE_BOTTOM,
        "5": TileTypes.ICE_TOP_RIGHT,
        "6": TileTypes.ICE_TOP_LEFT,
        "7": TileTypes.ICE_BOTTOM_RIGHT,
        "8": TileTypes.ICE_BOTTOM_LEFT,
        "\\": TileTypes.ROCK_END_RIGHT,
        "/": TileTypes.ROCK_END_LEFT,
    }

    def __init__(self, name, parent):
        self.size = Point(120, 50)
        self.data = [[TileTypes.SNOW for i in xrange(self.size.y)] for j in xrange(self.size.x)]
        self.object_cache = {}
        self.object_list = []
        self.actors = []
        self.doors = []
        self.robots = []
        self.parent = parent
        y = self.size.y - 1
        robot_positions = []
        self.axe_position = Point(random.randint(16, 44), random.randint(34, 43))
        with open(globals.pyinst.path(name)) as f:
            last = None
            for line in f:
                line = line.strip("\n")
                if len(line) < self.size.x:
                    line += " " * (self.size.x - len(line))
                if len(line) > self.size.x:
                    line = line[: self.size.x]
                for inv_x, tile in enumerate(line[::-1]):
                    x = self.size.x - 1 - inv_x

                    # try:
                    if 1:
                        # hack, also give the adjacent tile so we know what kind of background to put it on...
                        td = TileDataFactory(self, self.input_mapping[tile], Point(x, y), last, parent)
                        if td.type in TileTypes.Doors or td.type == TileTypes.CANDY_CANE:
                            self.doors.append(td)
                        last = self.input_mapping[tile]
                        for tile_x in xrange(td.size.x):
                            for tile_y in xrange(td.size.y):
                                if x + tile_x >= len(self.data) or y + tile_y >= len(self.data[x + tile_x]):
                                    continue
                                if self.data[x + tile_x][y + tile_y] != TileTypes.SNOW:
                                    self.data[x + tile_x][y + tile_y].Delete()
                                    self.data[x + tile_x][y + tile_y] = TileTypes.SNOW
                                if self.data[x + tile_x][y + tile_y] == TileTypes.SNOW:
                                    self.data[x + tile_x][y + tile_y] = td
                        if self.input_mapping[tile] == TileTypes.ACTIVATING_ROBOT:
                            robot_positions.append((Point(x + 0.2, y), actors.ActivatingRobot, 0))
                        if self.input_mapping[tile] == TileTypes.BASHING_ROBOT:
                            robot_positions.append((Point(x + 0.2, y), actors.BashingRobot, math.pi * 0.5))
                        if self.input_mapping[tile] == TileTypes.ENEMY:
                            self.parent.enemy_positions.append(Point(x + 0.2, y))
                    # except KeyError:
                    #    raise globals.types.FatalError('Invalid map data')
                y -= 1
                if y < 0:
                    break
        if not robot_positions:
            raise Exception("No robots defined")
        for pos, c, angle in robot_positions:
            robot = c(self, pos)
            robot.set_angle(angle)
            self.robots.append(robot)
            self.actors.append(robot)
        self.current_robot = self.robots[1]
        self.current_robot.Select()
        self.current_robot_index = 1

    def next_robot(self):
        self.current_robot.UnSelect()
        self.current_robot_index = (self.current_robot_index + 1) % len(self.robots)
        self.current_robot = self.robots[self.current_robot_index]
        self.current_robot.Select()
        return self.current_robot

    def AddObject(self, obj):
        self.object_list.append(obj)
        # Now for each tile that the object touches, put it in the cache
        for tile in obj.CoveredTiles():
            self.object_cache[tile] = obj

    def AddActor(self, pos, actor):
        try:
            self.data[pos.x][pos.y].AddActor(actor)
        except IndexError:
            pass

    def RemoveActor(self, pos, actor):
        try:
            self.data[pos.x][pos.y].RemoveActor(actor)
        except IndexError:
            pass

    def get_tile_from_world(self, pos):
        pos = (pos / globals.tile_dimensions).to_int()
        try:
            return self.data[pos.x][pos.y]
        except IndexError:
            return None


class TimeOfDay(object):
    def __init__(self, t):
        self.Set(t)

    def Set(self, t):
        self.t = t

    def Daylight(self):
        # Direction will be
        a_k = 0.2
        d_k = 0.4
        r = 1000
        b = -1.5
        t = (self.t + 0.75) % 1.0
        a = t * math.pi * 2
        z = math.sin(a) * r
        p = math.cos(a) * r
        x = math.cos(b) * p
        y = math.sin(b) * p
        if t < 0.125:
            # dawn
            colour = [d_k * math.sin(40 * t / math.pi) for i in (0, 1, 2)]
            colour[2] *= 1.4
            ambient = [a_k * math.sin(40 * t / math.pi) for i in (0, 1, 2)]
        elif t < 0.375:
            # daylight
            colour = (d_k, d_k, d_k)
            ambient = (a_k, a_k, a_k)
        elif t < 0.5:
            # dusk
            colour = (d_k * math.sin(40 * (t + 0.25) / math.pi) for i in (0, 1, 2))
            ambient = [a_k * math.sin(40 * (t + 0.25) / math.pi) for i in (0, 1, 2)]
        else:
            x, y, z = (1, 1, 1)
            colour = (0, 0, 0)
            ambient = (0, 0, 0)

        return (-x, -y, -z), colour, ambient, ambient[0] / a_k

    def Ambient(self):
        t = (self.t + 0.75) % 1.0
        return (0.5, 0.5, 0.5)

    def Nightlight(self):
        # Direction will be

        return (1, 3, -5), (0.25, 0.25, 0.4)


class RecvWindow(ui.UIElement):
    max_width = 23

    def __init__(self, parent, bl, tr, colour):
        super(RecvWindow, self).__init__(parent, bl, tr)
        self.colour = colour
        self.border = ui.Border(self, Point(0, 0), Point(1, 1), colour=self.colour, line_width=2)
        num_rows = 10
        self.rows = []
        margin_height = 0.02
        margin_width = -0.05
        height = (1.0 - 2 * margin_height) / num_rows
        self.current_row = 0
        self.row_text = [[] for i in xrange(num_rows)]
        for i in xrange(num_rows):
            row = ui.TextBox(
                parent=self,
                bl=Point(margin_width, margin_height + i * height),
                tr=Point(1 - margin_width, margin_height + (i + 1) * height),
                text=" ",
                scale=8,
                colour=self.colour,
            )
            self.rows.insert(0, row)

        self.add_message("Mission: Find large\ncandy source\nTab to switch robot\n>")

    def add_message(self, message):
        for letter in message:
            if letter == "\n":
                self.new_line()
            else:
                self.add_letter(letter)

    def new_line(self):
        if self.current_row < len(self.rows) - 1:
            self.current_row += 1
            return
        # Once we're at the bottom we stay at the bottom and just move everything up
        self.row_text = self.row_text[1:] + [[]]
        for i, row in enumerate(self.rows):
            row.SetText("".join(self.row_text[i]) if self.row_text[i] else " ")

    def add_letter(self, k):
        row = self.rows[self.current_row]
        text = self.row_text[self.current_row]
        if len(text) > self.max_width:
            self.new_line()
            return self.add_letter(k)

        text.append(k)
        row.SetText("".join(text))


class TabStates:
    FORMING_LETTER = 0
    FORMING_WORD = 1
    SWITCH_ROBOT = 2


class GameView(ui.RootElement):
    def __init__(self, send_morse, recv_morse):
        self.morse = send_morse
        self.recv_morse = recv_morse
        self.recv_morse.play("Any key to key\n>")
        self.atlas = globals.atlas = drawing.texture.TextureAtlas("tiles_atlas_0.png", "tiles_atlas.txt")
        self.enemies = []
        globals.ui_atlas = drawing.texture.TextureAtlas("ui_atlas_0.png", "ui_atlas.txt", extra_names=False)
        self.enemy_positions = []

        self.viewpos = Viewpos(Point(100, 200))
        self.game_over = False
        self.mouse_world = Point(0, 0)
        self.mouse_pos = Point(0, 0)
        self.command_stub = "Command:"
        self.command = []
        pygame.mixer.music.load(globals.pyinst.path("music.ogg"))
        self.music_playing = False
        super(GameView, self).__init__(Point(0, 0), globals.screen)
        # skip titles for development of the main game

        self.light = drawing.Quad(globals.light_quads)
        self.light.SetVertices(Point(0, 0), globals.screen_abs - Point(0, 0), 0)
        self.nightlight = drawing.Quad(globals.nightlight_quads)
        self.nightlight.SetVertices(Point(0, 0), globals.screen_abs - Point(0, 0), 0.5)
        self.timeofday = TimeOfDay(0.30)
        # self.mode = modes.LevelOne(self)
        self.StartMusic()
        # self.fixed_light = actors.FixedLight( Point(11,38),Point(26,9) )
        self.text_colour = (0, 1, 0, 1)
        barColours = [
            drawing.constants.colours.red,
            drawing.constants.colours.yellow,
            drawing.constants.colours.light_green,
        ]
        barBorder = drawing.constants.colours.white
        self.bottom_panel = ui.Box(
            parent=globals.screen_root, pos=Point(0, 0.0), tr=Point(1, 0.08), colour=(0, 0, 0, 0.8)
        )
        self.transmission = ui.TextBox(
            parent=self.bottom_panel,
            bl=Point(0, 0),
            tr=Point(0.12, 0.7),
            text="Send:",
            scale=10,
            colour=self.text_colour,
        )
        self.morse_entry = ui.TextBox(
            parent=self.bottom_panel,
            bl=Point(0.08, 0),
            tr=Point(0.35, 0.7),
            text=" ",
            scale=10,
            colour=self.text_colour,
        )
        self.command_text = ui.TextBox(
            parent=self.bottom_panel,
            bl=Point(0.35, 0),
            tr=Point(0.7, 0.7),
            text=self.command_stub,
            scale=10,
            colour=self.text_colour,
        )

        self.send_morse_light = ui.ToggleBox(
            parent=self.bottom_panel,
            pos=Point(0.71, 0),
            tr=Point(0.75, 1),
            on_tc=globals.ui_atlas.TextureUiCoords("light_on.png"),
            off_tc=globals.ui_atlas.TextureUiCoords("light_off.png"),
            buffer=globals.screen_texture_buffer,
        )

        self.receive_morse_light = ui.ToggleBox(
            parent=self.bottom_panel,
            pos=Point(0.75, 0),
            tr=Point(0.79, 1),
            on_tc=globals.ui_atlas.TextureUiCoords("red_light_on.png"),
            off_tc=globals.ui_atlas.TextureUiCoords("light_off.png"),
            buffer=globals.screen_texture_buffer,
        )
        self.letter_left = ui.TextBox(
            parent=self.bottom_panel,
            bl=Point(0.8, 0.5),
            tr=Point(1, 0.85),
            text="Press TAB to:",
            scale=6,
            colour=self.text_colour,
            alignment=drawing.texture.TextAlignments.CENTRE,
        )

        self.tab_action = ui.TextBox(
            parent=self.bottom_panel,
            bl=Point(0.8, 0),
            tr=Point(1, 0.35),
            text="Switch Robot",
            scale=6,
            colour=self.text_colour,
            alignment=drawing.texture.TextAlignments.CENTRE,
        )
        self.tab_state = TabStates.SWITCH_ROBOT

        self.robot_info = ui.Box(
            parent=globals.screen_root, pos=Point(0.7, 0.08), tr=Point(1, 1), colour=(0, 0, 0, 0.8)
        )

        self.morse_key = ui.UIElement(parent=self.robot_info, pos=Point(0, 0), tr=Point(1, 0.4))
        self.morse.create_key(self.morse_key, self.text_colour)

        self.recv_window = RecvWindow(
            parent=self.robot_info, bl=Point(0, 0.7), tr=Point(1, 1), colour=self.text_colour
        )

        self.robot_window = ui.UIElement(parent=self.robot_info, pos=Point(0, 0.40), tr=Point(1, 0.7))
        self.robot_window.border = ui.Border(
            self.robot_window, Point(0, 0), Point(1, 1), colour=self.text_colour, line_width=2
        )

        self.morse.register_light(self.send_morse_light)
        self.recv_morse.register_light(self.receive_morse_light)

        self.map = GameMap("level1.txt", self)
        self.mode = modes.GameMode(self)
        self.map.world_size = self.map.size * globals.tile_dimensions

        for pos in self.enemy_positions:
            self.enemies.append(actors.Enemy(self.map, pos))

    def morse_key_down(self):
        self.morse.key_down(globals.time)

    def morse_key_up(self):
        self.morse.key_up(globals.time)

    def StartMusic(self):
        # globals.sounds.stop_talking()
        # globals.sounds.talking_intro.play()
        pygame.mixer.music.play(-1)
        pygame.mixer.music.set_volume(globals.music_volume)
        self.music_playing = True

    def remove_enemy(self, to_remove):
        self.enemies = [enemy for enemy in self.enemies if enemy is not to_remove]

    def Draw(self):
        drawing.ResetState()
        drawing.Translate(-self.viewpos.pos.x, -self.viewpos.pos.y, 0)
        drawing.DrawAll(globals.quad_buffer, self.atlas.texture)
        # drawing.DrawAll(globals.nonstatic_text_buffer,globals.text_manager.atlas.texture)

    def send_command(self):
        self.map.current_robot.execute_command("".join(self.command))
        self.command = []
        self.command_text.SetText(self.command_stub)

    def tab_key(self):
        if self.morse.forming_letter():
            letter = self.morse.finish_letter()
            if letter == 4:
                letter = True
            if letter and letter != True:
                self.command.append(letter)
                self.command_text.SetText(self.command_stub + "".join(self.command).upper())

        elif self.command:
            self.send_command()
        else:
            self.next_robot()

    def Update(self, t):
        if self.mode:
            self.mode.Update(t)

        if self.game_over:
            return
        self.morse.update(t)

        if self.morse.forming_letter():
            if self.tab_state != TabStates.FORMING_LETTER:
                self.tab_action.SetText("Finish Letter")
                self.tab_state = TabStates.FORMING_LETTER
        elif self.command:
            if self.tab_state != TabStates.FORMING_WORD:
                self.tab_action.SetText("Send Command")
                self.tab_state = TabStates.FORMING_WORD
        elif self.tab_state != TabStates.SWITCH_ROBOT:
            self.tab_action.SetText("Switch Robot")
            self.tab_state = TabStates.SWITCH_ROBOT

        r = self.recv_morse.update(t)
        if r:
            if r == True or r == "\n":
                self.recv_window.new_line()
            elif r == 4:
                pass
            else:
                self.recv_window.add_letter(r)

        guess = "".join(self.morse.guess)
        if guess != self.morse_entry.text:
            if guess:
                self.morse_entry.SetText(guess)
            else:
                self.morse_entry.SetText(" ")

        self.t = t
        self.viewpos.Update(t)

        if self.viewpos._pos.x < 0:
            self.viewpos._pos.x = 0
        if self.viewpos._pos.y < 0:
            self.viewpos._pos.y = 0
        if self.viewpos._pos.x > (self.map.world_size.x - globals.screen.x):
            self.viewpos._pos.x = self.map.world_size.x - globals.screen.x
        if self.viewpos._pos.y > (self.map.world_size.y - globals.screen.y):
            self.viewpos._pos.y = self.map.world_size.y - globals.screen.y

        self.mouse_world = self.viewpos.pos + self.mouse_pos
        for robot in self.map.robots:
            robot.Update(t)

    def next_robot(self):
        robot = self.map.next_robot()
        self.viewpos.Follow(globals.time, robot)

    def GameOver(self):
        self.game_over = True
        self.mode = modes.GameOver(self)

    def KeyDown(self, key):
        self.mode.KeyDown(key)

    def KeyUp(self, key):
        if key == pygame.K_DELETE:
            if self.music_playing:
                self.music_playing = False
                pygame.mixer.music.set_volume(0)
            else:
                self.music_playing = True
                pygame.mixer.music.set_volume(globals.music_volume)
        self.mode.KeyUp(key)

    def MouseMotion(self, pos, rel, handled):
        world_pos = self.viewpos.pos + pos
        self.mouse_pos = pos

        self.mode.MouseMotion(world_pos, rel)

        return super(GameView, self).MouseMotion(pos, rel, handled)

    def MouseButtonDown(self, pos, button):
        if self.mode:
            pos = self.viewpos.pos + pos
            return self.mode.MouseButtonDown(pos, button)
        else:
            return False, False

    def MouseButtonUp(self, pos, button):
        if self.mode:
            pos = self.viewpos.pos + pos
            return self.mode.MouseButtonUp(pos, button)
        else:
            return False, False
