from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import sys

class Mode(object):
    """ Abstract base class to represent game modes """
    def __init__(self,parent):
        self.parent = parent

    def KeyDown(self,key):
        pass

    def MouseMotion(self,pos,rel):
        pass

    def KeyUp(self,key):
        pass

    def MouseButtonDown(self,pos,button):
        return False,False

    def MouseButtonUp(self,pos,button):
        return False, False

    def Update(self,t):
        pass

class TitleStages(object):
    STARTED  = 0
    COMPLETE = 1
    TEXT     = 2
    SCROLL   = 3
    WAIT     = 4

class Titles(Mode):
    blurb = "Director Morse"
    def __init__(self,parent):
        self.parent          = parent
        self.start           = pygame.time.get_ticks()
        self.stage           = TitleStages.STARTED
        self.handlers        = {TitleStages.STARTED  : self.Startup,
                                TitleStages.COMPLETE : self.Complete}
        bl = self.parent.GetRelative(Point(0,0))
        tr = bl + self.parent.GetRelative(globals.screen)
        self.blurb_text = ui.TextBox(parent = self.parent,
                                     bl     = bl         ,
                                     tr     = tr         ,
                                     text   = self.blurb ,
                                     textType = drawing.texture.TextTypes.GRID_RELATIVE,
                                     colour = (1,1,1,1),
                                     scale  = 4)
        self.backdrop        = ui.Box(parent = globals.screen_root,
                                      pos    = Point(0,0),
                                      tr     = Point(1,1),
                                      colour = (0,0,0,0))
        self.backdrop.Enable()

    def KeyDown(self,key):
        self.stage = TitleStages.COMPLETE

    def Update(self,t):
        self.elapsed = t - self.start
        self.stage = self.handlers[self.stage](t)
        self.stage = TitleStages.COMPLETE

    def Complete(self,t):
        self.backdrop.Delete()
        self.blurb_text.Delete()
        self.parent.mode = self.parent.game_mode = GameMode(self.parent)
        self.parent.viewpos.Follow(globals.time,self.parent.map.player)
        self.parent.StartMusic()

    def Startup(self,t):
        return TitleStages.STARTED

class GameMode(Mode):
    speed = 10
    angle_amounts = {pygame.K_LEFT  : 0.01*speed,
                     pygame.K_RIGHT : -0.01*speed}
    direction_amounts = {pygame.K_UP    : Point( 0.00, 10*speed),
                         pygame.K_DOWN  : Point( 0.00,-10*speed)}
    class KeyFlags:
        LEFT  = 1
        RIGHT = 2
        UP    = 4
        DOWN  = 8

    keyflags = {pygame.K_LEFT  : KeyFlags.LEFT,
                pygame.K_RIGHT : KeyFlags.RIGHT,
                pygame.K_UP    : KeyFlags.UP,
                pygame.K_DOWN  : KeyFlags.DOWN}

    def __init__(self,parent):
        self.parent            = parent
        self.keydownmap = {}
        self.parent.viewpos.Follow(globals.time,self.parent.map.current_robot)

    def KeyDown(self,input_key):
        key = input_key
        if 0 and key in self.keyflags:
            if self.keyflags[key] in self.keydownmap:
                return
            if key in self.angle_amounts:
                self.keydownmap[self.keyflags[key]] = input_key
                self.parent.map.current_robot.angle_speed += self.angle_amounts[key]
            elif key in self.direction_amounts:
                self.keydownmap[self.keyflags[key]] = input_key
                self.parent.map.current_robot.move_direction += self.direction_amounts[key]
        elif key in [pygame.K_TAB,pygame.K_SPACE]:
            pass
        else:
            self.parent.morse_key_down()

    def KeyUp(self,input_key):
        key = input_key
        if 0 and key in self.keyflags:
            if self.keyflags[key] not in self.keydownmap:
                return
            if key in self.angle_amounts and (self.keydownmap[self.keyflags[key]] == input_key):
                del self.keydownmap[self.keyflags[key]]
                self.parent.map.current_robot.angle_speed -= self.angle_amounts[key]
            elif key in self.direction_amounts and (self.keydownmap[self.keyflags[key]] == input_key):
                del self.keydownmap[self.keyflags[key]]
                self.parent.map.current_robot.move_direction -= self.direction_amounts[key]
        elif key == pygame.K_TAB:
            self.parent.next_robot()

        elif key == pygame.K_SPACE:
            if hasattr(self.parent.map.current_robot,'activate'):
                self.parent.map.current_robot.activate()
        else:
            self.parent.morse_key_up()

    def MouseButtonDown(self,pos,button):
        self.parent.map.current_robot.click(pos,button)
        return False,False

    def MouseButtonUp(self,pos,button):
        self.parent.map.current_robot.unclick(pos,button)
        return False,False

class FallingItem(object):
    def __init__(self,right=False):

        self.pos = globals.screen_abs*Point(1.0 if right else random.random(),random.random()*2 if right else random.random())
        self.radius = 64
        self.angle = random.random()*math.pi*2
        self.quad = drawing.Quad(globals.screen_texture_buffer,tc = globals.ui_atlas.TextureUiCoords('candy_cane.png'))
        self.set_pos(self.pos, self.angle)
        self.move_speed = Point(-1 +(random.random()-0.5)*0.2,-0.5+ (random.random()-0.5)*0.2)*3
        self.rotation_speed = (random.random()-0.5)*0.1
        self.dead = False
        self.last_update = None

    def set_pos(self,pos,angle):
        self.pos = pos
        self.angle = angle
        vertices = []
        for i in xrange(4):
            r = cmath.rect(self.radius,self.angle + (math.pi*(i*0.5 + 0.25)))
            vertices.append(self.pos + Point(r.real, r.imag))
        self.quad.SetAllVertices(vertices,100)

    def Update(self):
        if self.dead:
            return False
        if self.last_update == None:
            self.last_update = globals.time
            return True
        elapsed = globals.time - self.last_update
        self.last_update = globals.time
        amount = Point(self.move_speed.x*elapsed*0.03,self.move_speed.y*elapsed*0.03)
        target = self.pos + amount
        new_angle = self.angle + self.rotation_speed*elapsed*0.03
        self.set_pos(target, new_angle)

    def Delete(self):
        self.quad.Delete()
        self.dead = True


class GameOver(Mode):
    blurb = "Oh no, you managed to kill your robots somehow"
    def __init__(self,parent):
        self.parent          = parent
        self.blurb           = self.blurb
        self.blurb_text      = None
        self.handlers        = {TitleStages.TEXT    : self.TextDraw,
                                TitleStages.SCROLL  : self.Wait,
                                TitleStages.WAIT    : self.Wait}
        self.backdrop        = ui.Box(parent = globals.screen_root,
                                      pos    = Point(0,0),
                                      tr     = Point(1,1),
                                      colour = (0,0,0,0.6))

        bl = self.parent.GetRelative(Point(0,0))
        tr = bl + self.parent.GetRelative(globals.screen)
        self.blurb_text = ui.TextBox(parent = globals.screen_root,
                                     bl     = bl         ,
                                     tr     = tr         ,
                                     text   = self.blurb ,
                                     colour = (1,0,0,1),
                                     textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                     scale  = 30)

        self.start = None
        self.blurb_text.EnableChars(0)
        self.stage = TitleStages.TEXT
        self.played_sound = False
        self.skipped_text = False
        self.letter_duration = 20
        self.continued = False
        self.falling_items = []
        for i in xrange(100):
            self.falling_items.append(FallingItem())
        #pygame.mixer.music.load('end_fail.mp3')
        #pygame.mixer.music.play(-1)

    def Update(self,t):
        if self.start == None:
            self.start = t
        for item in self.falling_items:
            item.Update()
            if item.pos.x < 0 or item.pos.y < 0:
                item.Delete()
        orig = len(self.falling_items)
        self.falling_items = [item for item in self.falling_items if not item.dead]
        while len(self.falling_items) < orig:
            self.falling_items.append(FallingItem(right=True))

        self.elapsed = t - self.start
        try:
            self.stage = self.handlers[self.stage](t)
        except KeyError:
            return
        if self.stage == TitleStages.COMPLETE:
            return
            raise sys.exit('Come again soon!')

    def Wait(self,t):
        return self.stage

    def SkipText(self):
        if self.blurb_text:
            self.skipped_text = True
            self.blurb_text.EnableChars()

    def TextDraw(self,t):
        if not self.skipped_text:
            if self.elapsed < (len(self.blurb_text.text)*self.letter_duration) + 2000:
                num_enabled = int(self.elapsed/self.letter_duration)
                self.blurb_text.EnableChars(num_enabled)
            else:
                self.skipped_text = True
        elif self.continued:
            return TitleStages.COMPLETE
        return TitleStages.TEXT


    def KeyDown(self,key):
        #if key in [13,27,32]: #return, escape, space
        if not self.skipped_text:
            self.SkipText()
        else:
            self.continued = True

    def MouseButtonDown(self,pos,button):
        self.KeyDown(0)
        return False,False

class GameWin(GameOver):
    blurb = "You found the candy! Do the Robot Dance!"
