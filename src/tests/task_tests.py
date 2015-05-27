# 
# Copyright (c) 2014 Tom Carroll
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

'''
Test the basic Task stuff
'''
import json


from actuator.task import Task, TaskEngine, GraphableModelMixin, TaskException
from actuator.utils import reanimate_from_dict, persist_to_dict, _Persistable

#the callback_cache is used to help out with persistence/reanimation tests
#it provides a place to store callables which can't be persisted but can
#be looked up again and restored after a reanimate. THIS IS NOT GOOD GENERAL
#practice, but is put in place to support some of the odd test tests here
#
#keys are objects ids, values are 2-tuples of (perf_cb, rev_cb) from the
#TestTask object
callback_cache = {}

class TestTask(Task):
    def __init__(self, *args, **kwargs):
        super(TestTask, self).__init__(*args, **kwargs)
        self.perf_count = 0
        self.rev_count = 0
        self.pass_perf = True
        self.pass_rev = True
        self.perf_cb = None
        self.rev_cb = None
        self._orig_id_ = None
        
    def _get_attrs_dict(self):
        d = super(TestTask, self)._get_attrs_dict()
        callback_cache[id(self)] = (self.perf_cb, self.rev_cb)
        d.update( {"perf_count":self.perf_count,
                   "rev_count":self.rev_count,
                   "pass_perf":self.pass_perf,
                   "pass_rev":self.pass_rev,
                   "perf_cb":None,
                   "rev_cb":None,
                   "_orig_id_":id(self)} )
        return d
    
    def finalize_reanimate(self):
        self.perf_cb, self.rev_cb = callback_cache[self._orig_id_]
        
    def _perform(self, engine):
        if self.pass_perf:
            self.perf_count += 1
            if self.perf_cb:
                self.perf_cb(self)
        else:
            raise Exception("Perform failed as planned")
    
    def _reverse(self, engine):
        if self.pass_rev:
            self.rev_count += 1
            if self.rev_cb:
                self.rev_cb(self)
        else:
            raise Exception("Reverse failed as planned")
        
        
class FauxModel(GraphableModelMixin, _Persistable):
    def __init__(self):
        self.tasks = []
        self.dependencies = []
        
    def _get_attrs_dict(self):
        d = super(FauxModel, self)._get_attrs_dict()
        d["tasks"] = self.tasks
        d["dependencies"] = self.dependencies
        return d
    
    def _find_persistables(self):
        for t in self.tasks:
            for p in t.find_persistables():
                yield p
        for d in self.dependencies:
            for p in d.find_persistables():
                yield p
            
    def get_tasks(self):
        return self.tasks
    
    def add_task(self, task):
        self.tasks.append(task)
    
    def get_dependencies(self):
        return self.dependencies
    
    def add_dependency(self, dep):
        self.dependencies.append(dep)
        

def test001():
    """
    test001; nominal check of proper functioning of mock objects
    """
    fm = FauxModel()
    tt = TestTask("test001")
    fm.add_task(tt)
    te = TaskEngine("te1", fm, no_delay=True)
    te.perform_tasks()
    assert tt.perf_count == 1

def test002():
    """
    test002: basic test of reversing after perform
    """
    fm = FauxModel()
    tt = TestTask("test002")
    fm.add_task(tt)
    te = TaskEngine("te2", fm, no_delay=True)
    te.perform_tasks()
    te.perform_reverses()
    assert tt.perf_count == 1 and tt.rev_count == 1, ("perf_count=%d, rev_count=%d" %
                                                      (tt.perf_count, tt.rev_count))

def test003():
    """
    test003: two tasks, only one performs: reverse all
    """
    fm = FauxModel()
    tt1 = TestTask("test003a")
    tt1.pass_perf = True
    fm.add_task(tt1)
    tt2 = TestTask("test003b")
    tt2.pass_perf = False
    fm.add_task(tt2)
    fm.add_dependency(tt1 | tt2)
    te = TaskEngine("te3", fm, no_delay=True)
    try:
        te.perform_tasks()
        raise False, "A mock task should have raised an exception"
    except Exception, _:
        pass
#     te.perform_reverses()
#     only need the following to debug the above if it fails
    try:
        te.perform_reverses()
    except Exception, e:
        print e.message
        import traceback
        for t, et, ev, tb in te.get_aborted_tasks():
            print ">>>Task ", t.name
            traceback.print_exception(et, ev, tb, limit=10)
        assert False, "aborting-- reversing task raised"
    assert (tt1.perf_count == 1 and tt1.rev_count == 1  \
            and tt2.perf_count == 0 and tt2.rev_count == 0),   \
            "t1-pc=%d t1-rc=%d t2-pc=%d p2-rc=%d" %   \
            (tt1.perf_count, tt1.rev_count, tt2.perf_count, tt2.rev_count)
            
def test004():
    """
    test004: check dependencies between tasks
    """
    rev_order = []
    def order_check(task):
        rev_order.append(task.name)
    fm = FauxModel()
    tt1 = TestTask("test004a")
    tt1.rev_cb = order_check
    fm.add_task(tt1)
    tt2 = TestTask("test004b")
    tt2.rev_cb = order_check
    fm.add_task(tt2)
    fm.add_dependency(tt1 | tt2)
    te = TaskEngine("te4", fm, no_delay=True)
    te.perform_tasks()
    te.perform_reverses()
    assert rev_order == [tt2.name, tt1.name], str(rev_order)
    
def test005():
    "test005: check long dep chain in reversing"
    rev_order = []
    def order_check(task):
        rev_order.append(task.name)
    fm = FauxModel()
    tasks = []
    pt = None
    for i in range(5):
        tt = TestTask("test005-%d" % i)
        tt.rev_cb = order_check
        fm.add_task(tt)
        tasks.append(tt)
        if pt is not None:
            fm.add_dependency(pt | tt)
        pt = tt

    te = TaskEngine("te5", fm, no_delay=True)
    te.perform_tasks()
    te.perform_reverses()
    tasks.reverse()
    names = [t.name for t in tasks]
    assert rev_order == names
    
def test006():
    "test006: check more complex reverse graph"
    rev_order = []
    def order_check(task):
        rev_order.append(task.name)
    fm = FauxModel()
    tasks = []
    for i in range(6):
        tt = TestTask("t006-%d" % i)
        tt.rev_cb = order_check
        fm.add_task(tt)
        tasks.append(tt)
    fm.add_dependency(tasks[0] | tasks[1])
    fm.add_dependency(tasks[1] | tasks[2])
    fm.add_dependency(tasks[1] | tasks[3])
    fm.add_dependency(tasks[1] | tasks[4])
    fm.add_dependency(tasks[2] | tasks[4])
    fm.add_dependency(tasks[3] | tasks[4])
    fm.add_dependency(tasks[4] | tasks[5])
    
    te = TaskEngine("te6", fm, no_delay=True)
    te.perform_tasks()
    te.perform_reverses()
    tasks.reverse()
    assert (rev_order[0] == "t006-5" and rev_order[5] == "t006-0" and
            rev_order.index("t006-1") > rev_order.index("t006-2") and
            rev_order.index("t006-1") > rev_order.index("t006-3") and
            rev_order.index("t006-2") > rev_order.index("t006-4") and
            rev_order.index("t006-3") > rev_order.index("t006-4") and
            rev_order.index("t006-4") < 5), str(rev_order)
            
            

def test007():
    "test007: check more complex reverse graph after reanimation"
    rev_order = []
    def order_check(task):
        rev_order.append(task.name)
    fm = FauxModel()
    tasks = []
    for i in range(6):
        tt = TestTask("t007-%d" % i)
        tt.rev_cb = order_check
        fm.add_task(tt)
        tasks.append(tt)
    fm.add_dependency(tasks[0] | tasks[1])
    fm.add_dependency(tasks[1] | tasks[2])
    fm.add_dependency(tasks[1] | tasks[3])
    fm.add_dependency(tasks[1] | tasks[4])
    fm.add_dependency(tasks[2] | tasks[4])
    fm.add_dependency(tasks[3] | tasks[4])
    fm.add_dependency(tasks[4] | tasks[5])
    
    te = TaskEngine("te7", fm, no_delay=True)
    te.perform_tasks()
    d = persist_to_dict(fm)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    fmp = reanimate_from_dict(d)
    tep = TaskEngine("te7p", fmp, no_delay=True)
    try:
        tep.perform_reverses()
    except TaskException, e:
        print ">>>FAILED! tracebacks as follows:"
        import traceback
        for task, etype, value, tb in tep.get_aborted_tasks():
            print "----TB for task %s" % task.name
            traceback.print_exception(etype, value, tb)
    tasks.reverse()
    assert (rev_order[0] == "t007-5" and rev_order[5] == "t007-0" and
            rev_order.index("t007-1") > rev_order.index("t007-2") and
            rev_order.index("t007-1") > rev_order.index("t007-3") and
            rev_order.index("t007-2") > rev_order.index("t007-4") and
            rev_order.index("t007-3") > rev_order.index("t007-4") and
            rev_order.index("t007-4") < 5), str(rev_order)

def do_all():
    globs = globals()
    tests = []
    for k, v in globs.items():
        if k.startswith("test") and callable(v):
            tests.append(k)
    tests.sort()
    for k in tests:
        print "Doing ", k
        globs[k]()
            
if __name__ == "__main__":
    do_all()

