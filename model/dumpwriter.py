import subprocess, threading, json

class DumpWriter(object):

    def __init__(self, file : str, output : dict):
        self.file = file
        self.output=output

    def run(self):
        def target():
            with open(self.file, 'w') as f:
                f.write(json.dumps(self.output))
                
        thread = threading.Thread(target=target)
        thread.start()
