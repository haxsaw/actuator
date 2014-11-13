# The MIT License (MIT)
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
Created on Nov 13, 2014
'''

import sys
import json
import traceback
import actuator   #this must come before importing ansible; it patches subprocess
from ansible.runner import Runner


def run_from_json(json_msg):
    kwargs = json.loads(json_msg)
    runner = Runner(**kwargs)
    result = runner.run()
    return json.dumps(result)


if __name__ == "__main__":
    msg = sys.stdin.read()
    try:
        result = run_from_json(msg)
        sys.stdout.write(result)
        sys.stdout.flush()
    except Exception, e:
        sys.stderr.write(e.message)
        etype, evalue, tb = sys.exc_info()
        traceback.print_exception(etype, evalue, tb, file=sys.stderr)
        sys.stderr.flush()
    sys.exit(0)
