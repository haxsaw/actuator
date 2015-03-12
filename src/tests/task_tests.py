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

from actuator.task import Task, TaskEngine, GraphableModelMixin


class TestTask(Task):
    def __init__(self, *args, **kwargs):
        super(TestTask, self).__init__(*args, **kwargs)
        self.perf_count = 0
        self.rev_count = 0
        self.pass_perf = True
        self.pass_rev = True
        
    def _perform(self, engine):
        if self.pass_perf:
            self.perf_count += 1
        else:
            raise Exception("Perform failed as planned")
    
    def _reverse(self, engine):
        if self.pass_rev:
            self.rev_count += 1
        else:
            raise Exception("Reverse failed as planned")
        
        
class FauxModel(GraphableModelMixin):
    def __init__(self):
        self.tasks = []
        self.dependencies = []
        
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
    assert tt.perf_count == 1 and tt.rev_count == 1

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
    te = TaskEngine("te3", fm, no_delay=True)
    try:
        te.perform_tasks()
        raise False, "A mock task should have raised an exception"
    except Exception, _:
        pass
    try:
        te.perform_reverses()
    except Exception, e:
        print e.message
        import traceback
        for t, et, ev, tb in te.get_aborted_tasks():
            print ">>>Task ", t.name
            traceback.print_exception(et, ev, tb)
        assert False, "aborting reversing task raised"
    assert (tt1.perf_count == 1 and tt1.rev_count == 1
            and tt2.perf_count == 0 and tt2.rev_count == 0)

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

