import threading
from actuator.task import TaskEventHandler
from kivy.event import EventDispatcher


class TaskEventDispatcher(EventDispatcher):
    def __init__(self, tem, **kwargs):
        self.tem = tem
        self.register_event_type("on_redraw_task")
        super(TaskEventDispatcher, self).__init__(**kwargs)

    def task_event_received(self, tec, errtext=None):
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
        self.app = GT(graph, label=model.__class__.__name__)
        self.app.run()

    def engine_starting(self, model, graph):
        if self.app is None:
            self.app_thread = threading.Thread(target=self._fireup_display, args=(model, graph))
            self.app_thread.start()
        else:
            self.app.clear_graph()
            self.app.setup_for_graph(graph, label=model.__class__.__name__)
            self.app.render_graph()

    def task_starting(self, tec):
        self.ted.task_event_received(tec)

    def task_finished(self, tec):
        self.ted.task_event_received(tec)

    def task_retry(self, tec, errtext=None):
        self.ted.task_event_received(tec, errtext)

    def task_failed(self, tec, errtext=None):
        self.ted.task_event_received(tec, errtext)

    def update_task(self, tec, errtext=None):
        self.app.draw_node(tec, errtext)

    def update_graph(self):
        self.app.render_graph()
