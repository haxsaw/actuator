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

import time
import threading
from actuator.task import TaskEventHandler
from kivy.event import EventDispatcher


class TaskEventDispatcher(EventDispatcher):
    def __init__(self, tem, **kwargs):
        self.tem = tem
        self.register_event_type("on_redraw_task")
        super(TaskEventDispatcher, self).__init__(**kwargs)

    def task_event_received(self, model, tec, errtext=None):
        self.dispatch('on_redraw_task', tec, errtext)

    def on_redraw_task(self, tec, errtext=None):
        self.tem.update_task(tec, errtext)


class TaskEventManager(TaskEventHandler):
    def __init__(self):
        self.app = None
        self.app_thread = None
        self.ted = TaskEventDispatcher(self)

    def _fireup_display(self, model, graph):
        from hdisplay import GT
        app = GT(graph, label=model.__class__.__name__)
        self.app = app
        self.app.run()

    def engine_starting(self, model, graph):
        if self.app is None:
            self.app_thread = threading.Thread(target=self._fireup_display, args=(model, graph))
            self.app_thread.start()
        else:
            self.app.clear_graph()
            self.app.setup_for_graph(graph, label=model.__class__.__name__)
            self.app.render_graph()

    def task_starting(self, model, tec):
        self.ted.task_event_received(model, tec)

    def task_finished(self, model, tec):
        self.ted.task_event_received(model, tec)

    def task_retry(self, model, tec, errtext=None):
        self.ted.task_event_received(model, tec, errtext)

    def task_failed(self, model, tec, errtext=None):
        self.ted.task_event_received(model, tec, errtext)

    def update_task(self, tec, errtext=None):
        # FIXME this needs to have the model added.
        while self.app is None:
            # it's possible that events come in so fast that the display isn't ready yet; this is
            # only a startup issue, so a short delay will allow that startup to complete and then
            # we can smoothly delivery redraw events
            time.sleep(0.1)
        self.app.draw_node(tec, errtext)

    def update_graph(self):
        self.app.render_graph()
