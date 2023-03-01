from resultfilehandler import ResultFileHandler
import sys, getopt, os, libvirt, json
from dotenv import load_dotenv

STATE_ENDPOINT = ""
LIBVIRT_NODES = dict()

def read_endpoint():
    filehandler = ResultFileHandler()
    return filehandler.loadResult(STATE_ENDPOINT)

def display_status():
    status = read_endpoint()
    for hostname, host_status in status.items():
        print("###", hostname, "###")
        print("|> Tier2", round(host_status['cpu']['tier2'],2), "cores", round(host_status['mem']['tier2'],2), "MB")
        print("|> Tier1",round(host_status['cpu']['tier1'],2), "cores", round(host_status['mem']['tier1'],2), "MB")
        print("|> Tier0", round(host_status['cpu']['tier0'],2), "cores",  round(host_status['mem']['tier0'],2), "MB")

def deploy_vm_on_host(host: str, name : str, cpu : int, memory : int):
        try:
            conn = libvirt.open(LIBVIRT_NODES[host])
            print("Current VM on targeted host: ")
            for id in conn.listDomainsID():
                domain = conn.lookupByID(id)
                print(domain.name(), domain.info())
        except libvirt.libvirtError as e:
            print(repr(e), file=sys.stderr)
            exit(1)

def deploy_vm(name : str, cpu : int, memory : int):
    status = read_endpoint()
    host_found=False
    for hostname, host_status in status.items():
        if (host_status['cpu']['tier2']>cpu) and (host_status['mem']['tier2']>memory):
            host_found=True
            print("VM", name, "can be deployed on host", hostname)
    if(host_found):
        print("Deployment on", hostname)
        deploy_vm_on_host(hostname, name, cpu, memory)
    else:
        print("No host found")

if __name__ == '__main__':

    short_options = "hld:"
    long_options = ["help", "list","deploy="]
 
    try:
        arguments, values = getopt.getopt(sys.argv[1:], short_options, long_options)
    except getopt.error as err:
        print (str(err)) # Output error, and return with an error code
        sys.exit(2)

    load_dotenv()
    STATE_ENDPOINT = os.getenv('STATE_ENDPOINT')
    LIBVIRT_NODES = json.loads(os.getenv('LIBVIRT_NODES'))

    for current_argument, current_value in arguments:
        if current_argument in ("-l", "--list"):
            display_status()
        elif current_argument in ("-d", "--deploy"):
            config = current_value.split(',')
            try:
                name = config[0]
                cpu = int(config[1])
                memory = int(config[2])
                deploy_vm(name, cpu, memory)
            except Exception:
                print("python3 vmrequester.py [--help] [--list=''] [--deploy=name,cpu,mem")
        else:
            print("python3 vmrequester.py [--help] [--list=''] [--deploy=name,cpu,mem")
    
    sys.exit(0)