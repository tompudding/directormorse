from globals.types import Point
from OpenGL.GL import *
import globals
import ui
import drawing
import os
import game_view
import random
import pygame
import cmath
import math
import numpy
import modes


class Actor(object):
    texture = None
    width   = None
    height  = None
    threshold = 0.01
    initial_health = 100
    def __init__(self,map,pos):
        self.map            = map
        self.tc             = globals.atlas.TextureSpriteCoords('%s.png' % self.texture)
        self.quad           = drawing.Quad(globals.quad_buffer,tc = self.tc)
        self.size           = Point(float(self.width)/16,float(self.height)/16)
        self.corners = self.size, Point(-self.size.x,self.size.y), Point(-self.size.x,-self.size.y), Point(self.size.x,-self.size.y)
        self.corners        = [p*0.5 for p in self.corners]
        self.corners_polar  = [(p.length(),((1+i*2)*math.pi)/4) for i,p in enumerate(self.corners)]
        self.radius_square  = (self.size.x/2)**2 + (self.size.y/2)**2
        self.radius         = math.sqrt(self.radius_square)
        self.corners_euclid = [p for p in self.corners]
        self.current_sound  = None
        self.last_update    = None
        self.dead           = False
        self.move_speed     = Point(0,0)
        self.angle_speed    = 0
        self.move_direction = Point(0,0)
        self.pos = None
        self.last_damage = 0
        self.health = self.initial_health
        self.interacting = None
        self.SetPos(pos)
        self.set_angle(3*math.pi/2)

    def RemoveFromMap(self):
        if self.pos != None:
            bl = self.pos.to_int()
            tr = (self.pos+self.size).to_int()
            for x in xrange(bl.x,tr.x+1):
                for y in xrange(bl.y,tr.y+1):
                    self.map.RemoveActor(Point(x,y),self)

    def AdjustHealth(self,amount):
        self.health += amount
        if self.health > self.initial_health:
            self.health = self.initial_health
        if self.health < 0:
            #if self.dead_sound:
            #    self.dead_sound.play()
            self.health = 0
            self.dead = True
            self.Death()

    def damage(self, amount):
        if globals.time < self.last_damage + self.immune_duration:
            #woop we get to skip
            return
        self.last_damage = globals.time
        self.AdjustHealth(-amount)

    def SetPos(self,pos):
        self.RemoveFromMap()
        self.pos = pos

        self.vertices = [((pos + corner)*globals.tile_dimensions).to_int() for corner in self.corners_euclid]

        bl = pos
        tr = bl + self.size
        bl = bl.to_int()
        tr = tr.to_int()
        #self.quad.SetVertices(bl,tr,4)
        self.quad.SetAllVertices(self.vertices, 4)
        for x in xrange(bl.x,tr.x+1):
            for y in xrange(bl.y,tr.y+1):
                self.map.AddActor(Point(x,y),self)

    def TriggerCollide(self,other):
        pass


    def set_angle(self, angle):
        self.angle = angle%(2*math.pi)
        self.corners_polar  = [(p.length(),self.angle + ((1+i*2)*math.pi)/4) for i,p in enumerate(self.corners)]
        cnums = [cmath.rect(r,a) for (r,a) in self.corners_polar]
        self.corners_euclid = [Point(c.real,c.imag) for c in cnums]

    def Update(self,t):
        self.Move(t)

    def Move(self,t):
        if self.last_update == None:
            self.last_update = globals.time
            return
        elapsed = globals.time - self.last_update
        self.last_update = globals.time

        angle_change = self.angle_speed*elapsed*globals.time_step
        if 0 != self.required_turn:
            self.turned += abs(angle_change)
        self.set_angle(self.angle + angle_change)

        self.move_speed += self.move_direction.Rotate(self.angle)*elapsed*globals.time_step
        self.move_speed *= 0.7*(1-(elapsed/1000.0))

        if self.interacting:
            self.move_speed = Point(0,0)

        amount = Point(self.move_speed.x*elapsed*globals.time_step,self.move_speed.y*elapsed*globals.time_step)

        bl = self.pos.to_int()
        tr = (self.pos+self.size).to_int()
        for x in xrange(bl.x,tr.x+1):
            for y in xrange(bl.y,tr.y+1):
                try:
                    for actor in self.map.data[x][y].actors:
                        if actor is self:
                            continue
                        distance = actor.pos - self.pos
                        if distance.SquareLength() < self.radius_square + actor.radius_square:
                            overlap = self.radius + actor.radius - distance.length()
                            adjust = distance.unit_vector()*-overlap
                            #print type(self),self.radius,actor.radius,distance.length(),overlap,adjust
                            amount += adjust*0.1
                            self.TriggerCollide(actor)
                            #We've hit, so move us away from it's centre by the overlap
                except IndexError:
                    pass

        #check each of our four corners
        for corner in self.corners:
            pos = self.pos + corner
            target_x = pos.x + amount.x
            if target_x >= self.map.size.x:
                amount.x = 0
                target_x = pos.x
            elif target_x < 0:
                amount.x = -pos.x
                target_x = 0

            target_tile_x = self.map.data[int(target_x)][int(pos.y)]
            if target_tile_x.type in game_view.TileTypes.Impassable:
                amount.x = 0

            elif (int(target_x),int(pos.y)) in self.map.object_cache:
                obj = self.map.object_cache[int(target_x),int(pos.y)]
                if obj.Contains(Point(target_x,pos.y)):
                    amount.x = 0

            target_y = pos.y + amount.y
            if target_y >= self.map.size.y:
                amount.y = 0
                target_y = pos.y
            elif target_y < 0:
                amount.y = -pos.y
                target_y = 0
            target_tile_y = self.map.data[int(pos.x)][int(target_y)]
            if target_tile_y.type in game_view.TileTypes.Impassable:
                amount.y = 0
            elif (int(pos.x),int(target_y)) in self.map.object_cache:
                obj = self.map.object_cache[int(pos.x),int(target_y)]
                if obj.Contains(Point(pos.x,target_y)):
                    amount.y = 0


        self.SetPos(self.pos + amount)

        if self.interacting:
            diff = self.interacting.pos + (self.interacting.size*0.5) - self.pos
            distance = diff.length()
            if distance > 2.5:
                self.deactivate()

    def GetPos(self):
        return self.pos

    def GetPosCentre(self):
        return self.pos

    def click(self, pos, button):
        pass

    def unclick(self, pos, button):
        pass

    @property
    def screen_pos(self):
        p = (self.pos*globals.tile_dimensions - globals.game_view.viewpos._pos)*globals.scale
        return p


class Light(object):
    z = 60
    def __init__(self,pos,radius = 400, intensity = 1):
        self.radius = radius
        self.width = self.height = radius
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.colour = (1,1,1)
        self.intensity = float(intensity)
        self.set_pos(pos)
        self.on = True
        self.append_to_list()

    def append_to_list(self):
        globals.lights.append(self)

    def set_pos(self,pos):
        self.world_pos = pos
        pos = pos*globals.tile_dimensions
        self.pos = (pos.x,pos.y,self.z)
        box = (globals.tile_scale*Point(self.width,self.height))
        bl = Point(*self.pos[:2]) - box*0.5
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)

    def Update(self,t):
        pass

    @property
    def screen_pos(self):
        p = self.pos
        return ((p[0] - globals.game_view.viewpos._pos.x)*globals.scale.x,(p[1]-globals.game_view.viewpos._pos.y)*globals.scale.y,self.z)

class NonShadowLight(Light):
    def append_to_list(self):
        globals.non_shadow_lights.append(self)

class ActorLight(object):
    z = 6
    def __init__(self,parent):
        self.parent = parent
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.colour = (1,1,1)
        self.radius = 30
        self.intensity = 1
        self.on = True
        globals.non_shadow_lights.append(self)

    def Update(self,t):
        self.vertices = [((self.parent.pos + corner*2)*globals.tile_dimensions).to_int() for corner in self.parent.corners_euclid]
        self.quad.SetAllVertices(self.vertices, 0)

    @property
    def pos(self):
        return (self.parent.pos.x*globals.tile_dimensions.x,self.parent.pos.y*globals.tile_dimensions.y,self.z)

class FixedLight(object):
    z = 6
    def __init__(self,pos,size):
        #self.world_pos = pos
        self.pos = pos*globals.tile_dimensions
        self.size = size
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.colour = (0.2,0.2,0.2)
        self.on = True
        globals.uniform_lights.append(self)
        self.pos = (self.pos.x,self.pos.y,self.z)
        box = (self.size*globals.tile_dimensions)
        bl = Point(*self.pos[:2])
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)


class ConeLight(object):
    width = 700
    height = 700
    z = 60
    def __init__(self,pos,angle,width):
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.colour = (1,1,1)
        self.initial_angle = angle
        self.angle = angle
        self.angle_width = width
        self.on = True
        pos = pos*globals.tile_dimensions
        self.world_pos = pos
        self.pos = (pos.x,pos.y,self.z)
        box = (globals.tile_scale*Point(self.width,self.height))
        bl = Point(*self.pos[:2]) - box*0.5
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)
        globals.cone_lights.append(self)

    @property
    def screen_pos(self):
        p = self.pos
        out =  ((p[0] - globals.game_view.viewpos._pos.x)*globals.scale.x,(p[1]-globals.game_view.viewpos._pos.y)*globals.scale.y,self.z)
        return out

class Torch(ConeLight):
    def __init__(self,parent,offset):
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.parent = parent
        self.last_update    = None
        self.colour = (1,1,1)
        self.angle = 0.0
        self.offset = cmath.polar(offset.x + offset.y*1j)
        self.angle_width = 0.7
        self.on = True
        globals.cone_lights.append(self)

    @property
    def world_pos(self):
        offset = cmath.rect(self.offset[0],self.offset[1]+self.parent.angle)
        pos = (self.parent.pos + Point(offset.real,offset.imag))
        return (pos.x,pos.y,self.z)

    @property
    def pos(self):
        offset = cmath.rect(self.offset[0],self.offset[1]+self.parent.angle)
        pos = (self.parent.pos + Point(offset.real,offset.imag))*globals.tile_dimensions
        return (pos.x,pos.y,self.z)

    def Update(self,t):
        self.angle = (self.parent.angle + math.pi*0.5)%(2*math.pi)
        box = (globals.tile_scale*Point(self.width,self.height))
        bl = Point(*self.pos[:2]) - box*0.5
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)
        #self.quad.SetAllVertices(self.parent.vertices, 0)


class Robot(Actor):
    texture = 'robot'
    width = 16
    height = 16
    forward_speed = Point( 0.00, 0.04)
    rotation_speed = 0.04
    name = 'unknown'

    def __init__(self,map,pos):
        super(Robot,self).__init__(map,pos)
        self.light = ActorLight(self)
        self.info_window = self.map.parent.robot_window
        self.commands = {'f' : self.forward,
                         'b' : self.back,
                         'l' : self.left,
                         'r' : self.right}
        self.command_info = [('F<num>' , 'forward <num> units'),
                             ('B<num>' , 'back <num> units'),
                             ('L<num>' , 'turn left <num>'),
                             ('R<num>' , 'turn right <num>')]
        self.setup_info()
        self.move_end = None
        self.target_angle = self.angle
        self.turned = 0
        self.required_turn = 0
        offset = Point(-(self.width/globals.tile_dimensions.x)*0.6,0)
        self.torch = Torch(self,offset.Rotate(self.angle))

    def setup_info(self):
        #Title in the middle at the top
        self.info = ui.UIElement(parent=self.info_window,
                                 pos = Point(0,0),
                                 tr = Point(1,1))
        self.info.name = ui.TextBox(parent=self.info,
                                    bl=Point(0,0.8),
                                    tr=Point(1,1),
                                    text=self.name,
                                    scale=8,
                                    colour=self.map.parent.text_colour,
                                    alignment=drawing.texture.TextAlignments.CENTRE)
        num_rows = 10
        num_cols = 1
        margin_height_top = 0.1
        margin_height_bottom = 0.02
        margin_width  = -0.045
        height = (1.0-(margin_height_top+margin_height_bottom))/num_rows
        width  = (1.0-2*margin_width)/num_cols
        self.info.commands = []
        for i,(command,info) in enumerate(self.command_info):
            x = margin_width + (i/num_rows)*width
            y = margin_height_bottom + (num_rows - 1 - (i%num_rows))*height
            item = ui.TextBox(parent = self.info,
                              bl = Point(x,y),
                              tr = Point(x+width,y+height),
                              scale=6,
                              text = '%s: %s' % (command,info),
                              colour=self.map.parent.text_colour)
            self.info.commands.append(item)
        self.info.Disable()


    def Update(self,t):
        self.torch.Update(t)
        if self.move_end and t >= self.move_end:
            self.move_direction = Point(0,0)
        if self.turned > self.required_turn:
            self.angle_speed = 0
            self.turned = 0
            self.required_turn = 0
            self.angle = self.target_angle
            self.target_angle = 0
        super(Robot,self).Update(t)
        self.light.Update(t)

    def Select(self):
        self.info.Enable()

    def UnSelect(self):
        self.info.Disable()

    def move_command(self,command,multiplier):
        try:
            distance = int(command)
        except ValueError:
            globals.game_view.recv_morse.play('IN '+command)
            return
        self.move_direction = self.forward_speed*multiplier
        self.move_end = globals.time + (distance*600/abs(multiplier))
        globals.game_view.recv_morse.play('OK')

    def forward(self,command):
        self.move_command(command,1)

    def back(self,command):
        self.move_command(command,-0.6)

    def turn_command(self,command,multiplier):
        try:
            angle = float(command)*math.pi/180
        except ValueError:
            globals.game_view.recv_morse.play('IN '+command)
            return
        self.angle_speed = self.rotation_speed*multiplier
        self.target_angle = (self.angle + angle*multiplier)%(2*math.pi)
        self.required_turn = angle
        self.turned = 0
        globals.game_view.recv_morse.play('OK')

    def left(self,command):
        self.turn_command(command,1)

    def right(self,command):
        self.turn_command(command,-1)

    def execute_command(self,command):
        print 'Got command',command
        command = command.lower()
        command_name,command_data = command[:1],command[1:]
        try:
            self.commands[command_name](command_data)
        except KeyError:
            globals.game_view.recv_morse.play('UC '+command_name)


class ActivatingRobot(Robot):
    name = 'Activator'

    def setup_info(self):
        #Add special commands
        self.commands['a'] = self.activate
        self.commands['s'] = self.scan
        self.command_info.append( ('A','Activate') )
        self.command_info.append( ('S<angle>','Scan angle in front') )
        super(ActivatingRobot,self).setup_info()

    def activate(self):
        pass

    def scan(self):
        pass

class BashingRobot(Robot):
    name = 'Basher'

    def setup_info(self):
        #Add special commands
        self.commands['d'] = self.dig
        self.commands['h'] = self.hit
        self.commands['c'] = self.chop
        self.command_info.append( ('D','Dig for item') )
        self.command_info.append( ('H','Hit') )
        self.command_info.append( ('C','Chop with axe') )
        super(BashingRobot,self).setup_info()


    def dig(self):
        pass

    def hit(self):
        pass

    def chop(self):
        pass
