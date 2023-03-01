from collections import defaultdict
from dotenv import load_dotenv
import numpy as np
import threading, libvirt
import time, sys, getopt, os, json

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

# Global parameters
LIBVIRT_NODES = dict()
BALLOONING_GRACE_PERIOD_S=0
BALLOONING_SCOPE_S=0
BALLOONING_MIN_CONFIG_MB=0
BALLOONING_THRESHOLD_GAIN_MB=0
BALLOONING_SCOPE_SLEEP_S=0

#grace_period_tracker = defaultdict(lambda: int(time.time())) #default is current epoch in s
grace_period_tracker = defaultdict(lambda: int(0))

class RssReducer(object):

    def __init__(self, node : str, domain : str, mem_retrieval_threshold : int):
        self.node=node
        self.domain=domain
        self.mem_retrieval_threshold=int(mem_retrieval_threshold*1024)

    def run(self):
        conn = None
        def target():
            try:
                conn = libvirt.open(self.node)
            except libvirt.libvirtError as e:
                print(repr(e), file=sys.stderr)
                exit(1)
            dom = conn.lookupByName(self.domain)
            if(self.mem_retrieval_threshold<(BALLOONING_MIN_CONFIG_MB*1000)):
                self.mem_retrieval_threshold=(BALLOONING_MIN_CONFIG_MB*1000)
            if dom == None:
                print('Failed to find the domain '+ self.domain, file=sys.stderr)
                exit(1)
            print("Reduce", self.domain, "to", self.mem_retrieval_threshold, dom.setMemoryFlags(self.mem_retrieval_threshold,flags=libvirt.VIR_DOMAIN_AFFECT_LIVE))
            time.sleep(30)
            print("Increase", self.domain, "to", dom.maxMemory(), dom.setMemoryFlags(dom.maxMemory(),flags=libvirt.VIR_DOMAIN_AFFECT_LIVE))
            conn.close()

        thread = threading.Thread(target=target)
        thread.start()

def check_rss(domain : str, domain_metrics : dict):
    ## Check if VM is in grace period
    if (grace_period_tracker[domain] + BALLOONING_GRACE_PERIOD_S) > int(time.time()):
        print(domain, "is in grace period")
        return
    if "mem_usage" not in domain_metrics or not domain_metrics['mem_usage']:
        print(domain, "not enough data to proceed (lacking usage)") #can happen with new VMs
        return
    if "mem_rss" not in domain_metrics or not domain_metrics['mem_rss']:
        print(domain, "not enough data to proceed (lacking rss)")
        return
    mem_usage = np.percentile(domain_metrics['mem_usage'], 90)
    mem_rss = domain_metrics['mem_rss'][-1]
    mem_retrieval = mem_rss - mem_usage
    #print("debug", domain, domain_metrics['node'], mem_usage, mem_rss, mem_retrieval)
    if mem_retrieval > BALLOONING_THRESHOLD_GAIN_MB: # We can retrieve at least XGB
        print("geronimo")
        reducer = RssReducer(node=LIBVIRT_NODES[domain_metrics['node']], domain=domain, mem_retrieval_threshold=mem_usage)
        reducer.run()
        grace_period_tracker[domain] = int(time.time()) # update grace_period_tracker


def retrieve_domains_stats():
    myurl = os.getenv('INFLUXDB_URL')
    mytoken = os.getenv('INFLUXDB_TOKEN')
    myorg = os.getenv('INFLUXDB_ORG')
    mybucket = os.getenv('INFLUXDB_BUCKET')

    client = InfluxDBClient(url=myurl, token=mytoken, org=myorg)
    query_api = client.query_api()
    query = ' from(bucket:"' + mybucket + '")\
    |> range(start: -' + str(BALLOONING_SCOPE_S) + 's)\
    |> filter(fn: (r) => r["_measurement"] == "domain")'

    result = query_api.query(org=myorg, query=query)
    domains = defaultdict(lambda: defaultdict(list))

    for table in result:
        for record in table.records:
            domain_name = record.__getitem__('domain')
            domains[domain_name][record.get_field()].append(record.get_value())
            domains[domain_name]['node'] = record.__getitem__('url') # keep track of the host

    return domains

def main_loop():
    # Reduce its rss if needed
    while True:
        domains = retrieve_domains_stats()
        for domain_name, domain_stats in domains.items():
            check_rss(domain_name, domain_stats)
        time.sleep(30)

if __name__ == '__main__':

    short_options = "ho:du:"
    long_options = ["help", "output=","d","url="]

    try:
        arguments, values = getopt.getopt(sys.argv[1:], short_options, long_options)
    except getopt.error as err:
        print (str(err)) # Output error, and return with an error code
        sys.exit(2)
    for current_argument, current_value in arguments:
        if current_argument in ("-h", "--help"):
            print("python3 vmballooning.py [--help]")
            sys.exit(0)
    
    load_dotenv()
    LIBVIRT_NODES = json.loads(os.getenv('LIBVIRT_NODES'))
    BALLOONING_GRACE_PERIOD_S = int(os.getenv('BALLOONING_GRACE_PERIOD_S'))
    BALLOONING_SCOPE_S = int(os.getenv('BALLOONING_SCOPE_S'))
    BALLOONING_MIN_CONFIG_MB = int(os.getenv('BALLOONING_MIN_CONFIG_MB'))
    BALLOONING_THRESHOLD_GAIN_MB = int(os.getenv('BALLOONING_THRESHOLD_GAIN_MB'))
    BALLOONING_SCOPE_SLEEP_S = int(os.getenv('BALLOONING_SCOPE_SLEEP_S'))

    try:    
        main_loop()
    except KeyboardInterrupt:
        print("Program interrupted")