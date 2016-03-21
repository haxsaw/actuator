import threading
import time
from paramiko import (SSHClient, AutoAddPolicy)


def do_command(sh, cmd="ls -l"):
    time.sleep(0.1)
    sh.send("%s\n" % cmd)
    time.sleep(0.1)
    result = sh.recv(4096)
    print(""">>>>>>>>>>>>>>>Start results
%s
<<<<<<<<<<<<End results""" % result)
    
    
if __name__ == "__main__":
    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())
    client.connect(hostname="localhost", username="lxle1",
                   key_filename="./lxle1-dev-key")
    threads = []
    for i in [1, 2]:
        sh = client.invoke_shell()
        t = threading.Thread(target=do_command, args=(sh,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
