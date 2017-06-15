import json
from kivy.app import App
import networkx
from networkx.drawing.nx_agraph import graphviz_layout
from actuator.task import Task, TaskExecControl
from kivy.uix.widget import Widget
from kivy.properties import ObjectProperty
from kivy.graphics import Color, Ellipse, Line, Triangle
from kivy.base import EventLoop


g = networkx.DiGraph()
g.add_nodes_from([1, 2, 3, 4])
g.add_edges_from([(1, 2), (1, 3), (3, 4), (2, 4)])


class MarkerWidget(Widget):
    win_xysize = ObjectProperty([None, None])

    def __init__(self, pos, size, xyrange, win_xysize, color, **kwargs):
        self.size = size
        self.xyrange = xyrange
        self.win_xysize = win_xysize
        self.color = color
        self.circle = None
        self.bind(pos=self.redraw)
        self.bind(win_xysize=self.redraw)
        super(MarkerWidget, self).__init__(**kwargs)
        self.pos = pos

    def redraw(self, *args):
        xsize, ysize = self.win_xysize
        xrange, yrange = self.xyrange
        xpos = float(self.pos[0]) / float(xrange) * float(xsize)
        ypos = float(self.pos[1]) / float(yrange) * float(ysize)
        pos = (xpos, ypos)
        with self.canvas:
            Color(*self.color)
            if self.circle is None:
                self.circle = Ellipse(pos=pos, size=self.size)
            else:
                self.circle.pos = pos


class LineWidget(Widget):
    win_xysize = ObjectProperty([None, None])

    def __init__(self, startxy, endxy, xyrange, win_xysize, color, **kwargs):
        self.startxy = startxy
        self.endxy = endxy
        self.xyrange = xyrange
        self.color = color
        self.bind(win_xysize=self.redraw)
        self.line = None
        super(LineWidget, self).__init__(**kwargs)
        self.win_xysize = win_xysize

    def redraw(self, *args):
        xsize, ysize = self.win_xysize
        xrange, yrange = self.xyrange
        startx = float(self.startxy[0]) / float(xrange) * float(xsize)
        starty = float(self.startxy[1]) / float(yrange) * float(ysize)
        endx = float(self.endxy[0]) / float(xrange) * float(xsize)
        endy = float(self.endxy[1]) / float(yrange) * float(ysize)
        with self.canvas:
            Color(*self.color)
            if self.line is None:
                self.line = Line(points=[startx, starty, endx, endy])
            else:
                self.line.points = [startx, starty, endx, endy]


class GT(App):
    def __init__(self, g=None):
        super(GT, self).__init__()
        self.g = g
        if self.g is not None:
            self.positions = graphviz_layout(self.g, prog="dot")
        self.xmax = max([p[0] for p in self.positions.values()]) + 30
        self.ymax = max([p[1] for p in self.positions.values()]) + 30
        self.bl = None
        self.fig = None
        self.ax = None
        self.nav = None
        self.markers = {}
        self.lines = {}

    def setup_for_graph(self, graph):
        """
        configures the app to run a particular graph
        @param graph: instance of networkx.DiGraph
        @return:
        """
        self.g = graph
        self.positions = graphviz_layout(self.g, prog="dot")
        return self

    colors = {Task.UNSTARTED: (1.0, 1.0, 1.0),
              Task.PERFORMED: (0, 1.0, 0),
              Task.REVERSED: (1.0, 1.0, 1.0),
              TaskExecControl.UNPERFORMED: (1.0, 1.0, 1.0),
              TaskExecControl.FAIL_FINAL: (1.0, 0, 0),
              TaskExecControl.PERFORMING: (0, 0, 1.0),
              TaskExecControl.FAIL_RETRY: (1.0, 1.0, 0),
              TaskExecControl.SUCCESS: (0, 1.0, 0)
              }

    def draw_node(self, tec):
        if isinstance(tec, TaskExecControl):
            node = tec.task
            status = tec.status
        else:
            node = tec
            if isinstance(tec, Task):
                status = tec.performance_status
            else:   # this is nothing we can interpret; probably a number
                status = TaskExecControl.FAIL_FINAL

        x, y = self.positions[node]
        color = self.colors[status]
        screensize = EventLoop.window.size
        mw = self.markers.get(node)
        if mw is not None:
            if mw.win_xysize == screensize:
                # then this is a replace; dump the node and recreate it, possibly with a new color
                new_mw = MarkerWidget((x, y), (10, 10), (self.xmax, self.ymax), screensize, color)
                self.markers[node] = new_mw
                self.bl.remove_widget(mw)
                self.bl.add_widget(new_mw, index=0)
            else:
                # just update the screen size
                mw.win_xysize = screensize
        else:
            mw = MarkerWidget((x, y), (10, 10), (self.xmax, self.ymax), screensize, color)
            self.markers[node] = mw
            self.bl.add_widget(mw, index=0)

    def render_graph(self, *args):
        screensize = EventLoop.window.size
        for begin, end in self.g.edges():
            lw = self.lines.get((begin, end))
            if lw is None:
                bx, by = self.positions[begin]
                ex, ey = self.positions[end]
                lw = LineWidget((bx + 5, by + 5), (ex + 5, ey + 5), (self.xmax, self.ymax),
                                EventLoop.window.size, (1.0, 1.0, 1.0))
                self.lines[(begin, end)] = lw
                self.bl.add_widget(lw)
            else:
                lw.win_xysize = screensize

        for node in self.positions.keys():
            self.draw_node(node)

    def build(self):
        self.bl = Widget()
        # Window.bind()
        self.bl.bind(size=self.render_graph)

        return self.bl


def runnit(g):
    app = GT(g)
    app.run()


if __name__ == "__main__":
    # runnit(g)

    # bigger graph
    d = json.loads(open("hadoop_graph.json", "r").read())
    edges = d["edges"]
    nodes = d["nodes"]
    g = networkx.DiGraph()
    g.add_nodes_from(nodes)
    g.add_edges_from(edges)
    runnit(g)
