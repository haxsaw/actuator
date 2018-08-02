#
# Copyright (c) 2017 Tom Carroll
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import json
import math
from kivy.app import App
import networkx
from networkx.drawing.nx_agraph import graphviz_layout
from actuator.task import Task, TaskExecControl
from actuator.provisioners.core import ProvisioningTask
from actuator.config import ConfigTask
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.label import Label
from kivy.properties import ObjectProperty
from kivy.graphics import Color, Ellipse, Line, Triangle
from kivy.base import EventLoop


def compute_pos(opos, xyrange, win_xysize):
    """
    this method maps a position from one coordinate set to another

    The method takes an original xy position (opos) that is expressed in
    a coordinate space of absolute size named in xyrange and computes a new
    xy postion that falls into the same relative postion in a new coordinate
    space of size win_xysize. This allows data points that are in a range larger
    than a window's actual size to be mapped to a position in that window at
    relatively the same place. This effectively allows scaling up or down the
    postioning of a coordinate, depending on the relative sizes described in
    xyrange and win_xyrange.

    @param opos: sequence of length 2 that are an x-y coordinate in the source
        coordinate system
    @param xyrange: sequence of length 2 that represent the absolute size of
        the source coordinate system; that is, any value for opos would be able
        to be found within this range.
    @param win_xysize: sequence of length 2 that represents the destination
        coordinate system size. This is generally the size of window where
        something should be drawn
    @return: a 2-tuple of the mapped xy postion of the new point in the
        win_xysize coordinate system
    """
    xsize, ysize = win_xysize
    xrange, yrange = xyrange
    xpos = float(opos[0]) / float(xrange) * float(xsize)
    ypos = float(opos[1]) / float(yrange) * float(ysize)
    return xpos, ypos


def rotate_point(pivot, point, angle):
    # unpack things
    pivotx, pivoty = pivot
    pointx, pointy = point
    # translate to origin
    pointx -= pivotx
    pointy -= pivoty
    # compute trig values
    s = math.sin(angle)
    c = math.cos(angle)
    # rotate
    newx = pointx * c - pointy * s
    newy = pointx * s + pointy * c
    # translate back
    return newx + pivotx, newy + pivoty


class MarkerWidget(Widget):
    win_xysize = ObjectProperty([None, None])

    def __init__(self, opos, size, xyrange, win_xysize, color, select_handler, **kwargs):
        self.size = size
        self.xyrange = xyrange
        self.win_xysize = win_xysize
        self.color = color
        self.circle = None
        self.opos = opos
        self.pos = self.adjust_pos_for_marker(self.opos, self.size, self.xyrange, self.win_xysize)
        self.select_handler = select_handler
        self.bind(win_xysize=self.redraw)
        super(MarkerWidget, self).__init__(**kwargs)
        self.redraw()

    @staticmethod
    def adjust_pos_for_marker(opos, size, xyrange, win_xysize):
        pos = compute_pos(opos, xyrange, win_xysize)
        halfx = size[0] / 2.0
        halfy = size[1] / 2.0
        return pos[0] - halfx, pos[1] - halfy

    def on_touch_down(self, touch):
        xsize, ysize = self.size
        if ((self.pos[0] - xsize <= touch.x <= self.pos[0] + xsize) and
                (self.pos[1] - ysize <= touch.y <= self.pos[1] + ysize)):
            self.select_handler.marker_selected(self)

    def redraw(self, *_):
        pos = self.pos = self.adjust_pos_for_marker(self.opos, self.size, self.xyrange, self.win_xysize)
        with self.canvas:
            Color(*self.color)
            if self.circle is None:
                self.circle = Ellipse(pos=pos, size=self.size)
            else:
                self.circle.pos = pos


class LineWidget(Widget):
    win_xysize = ObjectProperty([None, None])
    hlen = 13  # length of arrow head

    def __init__(self, startxy, endxy, xyrange, win_xysize, color, **kwargs):
        self.startxy = startxy
        self.endxy = endxy
        self.xyrange = xyrange
        self.color = color
        self.bind(win_xysize=self.redraw)
        self.line = None
        self.triangle = None
        super(LineWidget, self).__init__(**kwargs)
        self.win_xysize = win_xysize

    def redraw(self, *_):
        startx, starty = compute_pos(self.startxy, self.xyrange, self.win_xysize)
        endx, endy = compute_pos(self.endxy, self.xyrange, self.win_xysize)
        with self.canvas:
            Color(*self.color)
            if not startx - endx:
                angle = math.radians(180)
            else:
                angle = math.atan((endy - starty) * 1.0 / (endx - startx) * 1.0) + \
                        math.atan(90) * (1 if (endx - startx < 0) else -1)
            if self.line is None:
                self.line = Line(points=[startx, starty, endx, endy])
                p = [endx, endy]
                p.extend(rotate_point((endx, endy), (endx-3, endy-self.hlen), angle))
                p.extend(rotate_point((endx, endy), (endx+3, endy-self.hlen), angle))
                self.triangle = Triangle(points=p)
            else:
                self.line.points = [startx, starty, endx, endy]
                p = [endx, endy]
                p.extend(rotate_point((endx, endy), (endx-3, endy-self.hlen), angle))
                p.extend(rotate_point((endx, endy), (endx+3, endy-self.hlen), angle))
                self.triangle.points = p


class GT(App):
    def __init__(self, g=None, label="unlabeled"):
        super(GT, self).__init__()
        self.g = self.xmax = self.ymax = self.bl = self.markers = self.lines = self.positions = \
            self.label = self.label_widget = self.node_errors = self.selected_label_widget = \
            self.info = None
        self.xoffset = 250
        self.setup_for_graph(g, label)
        self.node_color = {}

    def marker_selected(self, marker):
        nodes_by_marker = {v: k for k, v in self.markers.items()}
        node = nodes_by_marker.get(marker)
        if node is not None:
            if isinstance(node, Task):
                if isinstance(node, ConfigTask):
                    try:
                        role = node.get_task_role()
                    except:
                        role = None
                    msg = "Task {}, role {}".format(node.name, role.name if role else "unknown role")
                elif isinstance(node, ProvisioningTask):
                    msg = "Task {}, resource {}, cloud {}".format(
                        node.name, node.rsrc.get_display_name(), node.rsrc.cloud)
                else:   # don't know what this is
                    msg = "{} {}".format(node.__class__.__name__, node.name)
                error_text = "\n".join(self.node_errors.get(node, ["no errors"]))
                seltext = "{}\n{}".format(msg, error_text)
            else:
                seltext = "node %s" % str(node)
        else:
            seltext = "Can't find node!"
        self.selected_label_widget.text = seltext
        self.adjust_labels()

    def clear_graph(self):
        if self.bl:
            for m in self.markers.values():
                self.bl.remove_widget(m)
            self.markers.clear()
            for l in self.lines.values():
                self.bl.remove_widget(l)
            self.lines.clear()
            self.positions.clear()
            self.label_widget.text = ""
            self.selected_label_widget.text = ""
            self.node_color.clear()

    def setup_for_graph(self, g, label="unlabeled"):
        """
        configures the app to run a particular graph
        @param graph: instance of networkx.DiGraph
        @return:
        """
        self.g = g
        if self.g is not None:
            self.positions = graphviz_layout(self.g, prog="dot")
        self.xmax = max([p[0] for p in self.positions.values()]) + 30
        self.ymax = max([p[1] for p in self.positions.values()]) + 30
        self.markers = {}
        self.lines = {}
        self.node_errors = {}
        self.label = label
        if self.label_widget:
            self.label_widget.text = "%s\nprocessing progress" % label
        if self.selected_label_widget:
            self.selected_label_widget.text = ""

    colors = {Task.UNSTARTED: (1.0, 1.0, 1.0),
              Task.PERFORMED: (0, 1.0, 0),
              Task.REVERSED: (1.0, 1.0, 1.0),
              TaskExecControl.UNPERFORMED: (1.0, 1.0, 1.0),
              TaskExecControl.FAIL_FINAL: (1.0, 0, 0),
              TaskExecControl.PERFORMING: (0, 0, 1.0),
              TaskExecControl.FAIL_RETRY: (1.0, 1.0, 0),
              TaskExecControl.SUCCESS: (0, 1.0, 0)
              }

    def draw_node(self, tec, errtext=None):
        if isinstance(tec, TaskExecControl):
            node = tec.task
            status = tec.status
        else:
            node = tec
            if isinstance(tec, Task):
                status = tec.performance_status
            else:   # this is nothing we can interpret; probably a number
                status = TaskExecControl.FAIL_FINAL

        if errtext:
            self.node_errors[node] = errtext
        else:
            if node in self.node_errors:
                del self.node_errors[node]

        x, y = self.positions[node]
        color = self.colors[status]
        if color == self.colors[TaskExecControl.UNPERFORMED]:
            color = self.node_color.get(node, self.colors[TaskExecControl.UNPERFORMED])
        self.node_color[node] = color
        screeny = EventLoop.window.size[1]
        screenx = EventLoop.window.size[0] - self.info.size[0]
        screensize = (screenx, screeny)
        mw = self.markers.get(node)
        if mw is not None:
            if mw.win_xysize == screensize:
                # then this is a replace; dump the node and recreate it, possibly with a new color
                new_mw = MarkerWidget((x, y), (15, 10), (self.xmax, self.ymax), screensize, color, self)
                self.markers[node] = new_mw
                self.bl.remove_widget(mw)
                self.bl.add_widget(new_mw, index=0)
            else:
                # just update the screen size
                mw.win_xysize = screensize
        else:
            mw = MarkerWidget((x, y), (15, 10), (self.xmax, self.ymax), screensize, color, self)
            self.markers[node] = mw
            self.bl.add_widget(mw, index=0)

    def render_graph(self, *_):
        screeny = EventLoop.window.size[1]
        screenx = EventLoop.window.size[0] - self.info.size[0]
        screensize = (screenx, screeny)
        for begin, end in self.g.edges():
            lw = self.lines.get((begin, end))
            if lw is None:
                bx, by = self.positions[begin]
                ex, ey = self.positions[end]
                lw = LineWidget((bx, by), (ex, ey), (self.xmax, self.ymax),
                                screensize, (1.0, 1.0, 1.0))
                self.lines[(begin, end)] = lw
                self.bl.add_widget(lw)
            else:
                lw.win_xysize = screensize

        for node in self.positions.keys():
            self.draw_node(node, self.node_errors.get(node))

        self.adjust_labels()

    def resize_info(self, *args):
        self.info.size = (self.xoffset, EventLoop.window.size[1])

    def adjust_labels(self):
        self.selected_label_widget.texture_update()
        self.label_widget.pos = ((self.info.size[0] / 2 - self.label_widget.texture_size[0] / 2),
                                 (self.info.size[1] / 2 - self.label_widget.texture_size[1] / 2))

        ypos = (self.label_widget.pos[1] - (self.label_widget.texture_size[1] / 2) - 5 -
                (self.selected_label_widget.texture_size[1] / 2))
        self.selected_label_widget.pos = (-self.info.size[0] / 2 + self.selected_label_widget.texture_size[0] / 2, ypos)

    def build(self):
        self.root = BoxLayout(spacing=3, orientation="horizontal")
        self.bl = Widget(size_hint=(1, 1))
        self.root.add_widget(self.bl)
        self.bl.bind(size=self.render_graph)
        self.info = RelativeLayout(size=(self.xoffset, EventLoop.window.size[1]), size_hint=(None, None))
        self.root.add_widget(self.info)
        self.label_widget = Label(text="%s\nprocessing progress" % self.label, halign="right")
        self.label_widget.bind(size=lambda *_: self.label_widget.texture_size)
        self.info.add_widget(self.label_widget)
        self.selected_label_widget = Label(text="", halign="left", valign="top", text_size=(200, None))
        self.info.add_widget(self.selected_label_widget)
        EventLoop.window.bind(size=self.resize_info)
        EventLoop.window.size = (1024, 768)

        return self.root


def runnit(g, label="no label"):
    app = GT(g, label=label)
    app.run()


# for great testing!
if __name__ == "__main__":
    # teensy graph
    # g = networkx.DiGraph()
    # g.add_nodes_from([1, 2, 3, 4])
    # g.add_edges_from([(1, 2), (1, 3), (3, 4), (2, 4)])
    # runnit(g, "tiny")

    # bigger graph
    d = json.loads(open("hadoop_graph.json", "r").read())
    edges = d["edges"]
    nodes = d["nodes"]
    g = networkx.DiGraph()
    g.add_nodes_from(nodes)
    g.add_edges_from(edges)
    runnit(g, "hadoop snapshot")
