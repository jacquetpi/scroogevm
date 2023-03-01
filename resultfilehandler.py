import json

class ResultFileHandler:

    def loadResult(self, inputfile : str):
        with open(inputfile, 'r') as f:
            data = json.load(f)
        return data

    def writeResult(self, outputfile : str, results : dict):
        with open(outputfile, 'w') as f:
            f.write(json.dumps(results))