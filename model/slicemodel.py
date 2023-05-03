from model.slicevmwrapper import SliceVmWrapper
from model.slicehostwrapper import SliceHostWrapper
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from collections import defaultdict
from model.oversubscription_computation.vmbasedoversubscription import *
from model.oversubscription_computation.nodebasedoversubscription import *
import os

class SliceModel(object):

    def __init__(self, model_node_name : str, model_position : int, model_init_epoch : int, 
        model_historical_occurences : int, model_number_of_slice : int, leftBound : int, rightBound : int,
        cpu_percentile : int, mem_percentile : int, strategy : int, aggregation : int):
        #Data related to model
        self.model_historical_occurences=model_historical_occurences
        self.model_node_name=model_node_name
        self.model_position=model_position
        self.model_init_epoch=model_init_epoch
        self.model_number_of_slice=model_number_of_slice
        self.model_cpu_percentile=cpu_percentile
        self.model_mem_percentile=mem_percentile
        self.strategy=strategy
        self.model_aggregation=aggregation
        #Data related to slice
        self.leftBound=leftBound
        self.rightBound=rightBound
        self.size=rightBound-leftBound
        # Data itself:
        self.slicevmdata=dict()
        self.slicenodedata=SliceHostWrapper(self.model_node_name, historical_occurences=self.model_historical_occurences, cpu_percentile=self.model_cpu_percentile, mem_percentile=self.model_mem_percentile, strategy=self.strategy, aggregation=self.model_aggregation)
        self.cpu_tier0=None
        self.cpu_tier1=None
        self.cpu_tier2=None
        self.mem_tier0=None
        self.mem_tier1=None
        self.mem_tier2=None

    def build_past_slices_from_epoch(self, past_iteration : int = 1):
        for i in range((-past_iteration),0):
            self.build_slice_from_epoch(iteration=i)

    def build_slice_from_epoch(self, iteration : int):
        begin_epoch = self.model_init_epoch + ((iteration)*(self.model_number_of_slice*self.size)) + (self.model_position*self.size)
        end_epoch = begin_epoch + self.size
        self.add_slice_data_from_epoch(begin_epoch, end_epoch)

    def build_slice_from_dump(self, dump_data : dict, iteration : int):
        self.add_slice_data_from_dump(dump_data, iteration)

    def add_slice_data_from_epoch(self, begin_epoch : int, end_epoch : int):
        domain_data = self.retrieve_domain_data(begin_epoch, end_epoch)
        booked_cpu, booked_mem = 0, 0
        for domain_name, domain_stats in domain_data.items():
            if domain_name not in self.slicevmdata: # TODO : remove domain which left
                self.slicevmdata[domain_name]=SliceVmWrapper(domain_name=domain_name, historical_occurences=self.model_historical_occurences, cpu_percentile=self.model_cpu_percentile, mem_percentile=self.model_mem_percentile, aggregation=self.model_aggregation)
            booked_cpu+= domain_stats["cpu"][-1] if domain_stats["cpu"] else 0
            booked_mem+= domain_stats["mem"][-1] if domain_stats["mem"] else 0
            self.slicevmdata[domain_name].add_slice_data_from_raw(domain_stats)
        node_stats = self.retrieve_node_data(begin_epoch, end_epoch)
        node_stats["vm"] = list(domain_data.keys()) # vm id list
        node_stats["booked_cpu"] = booked_cpu
        node_stats["booked_mem"] = booked_mem
        self.slicenodedata.add_slice_data_from_raw(node_stats)
        self.update_cpu_mem_tiers()

    def add_slice_data_from_dump(self, dump_data : dict, occurence : int):
        booked_cpu, booked_mem = 0, 0
        if "vm" in dump_data:
            for domain_name, domain_dump_data in dump_data["vm"].items():
                if domain_name not in self.slicevmdata:
                    self.slicevmdata[domain_name]=SliceVmWrapper(domain_name=domain_name, historical_occurences=self.model_historical_occurences, cpu_percentile=self.model_cpu_percentile, mem_percentile=self.model_mem_percentile, aggregation=self.model_aggregation)
                added = self.slicevmdata[domain_name].add_slice_data_from_dump(domain_dump_data, occurence, epoch=dump_data["epoch"][occurence])
                if (added) and ('raw_data' in domain_dump_data) and occurence < len(domain_dump_data['raw_data']):
                    booked_cpu+= domain_dump_data["raw_data"][occurence]['cpu'][-1] if domain_dump_data["raw_data"][occurence].get('cpu', False) and domain_dump_data["raw_data"][occurence]['cpu'][-1] is not None else 0
                    booked_mem+= domain_dump_data["raw_data"][occurence]['mem'][-1] if domain_dump_data["raw_data"][occurence].get('mem', False) and domain_dump_data["raw_data"][occurence]['mem'][-1] is not None else 0                
        dump_data["node"]["booked_cpu"] = booked_cpu # can be avoided on newer trace
        dump_data["node"]["booked_mem"] = booked_mem
        self.slicenodedata.add_slice_data_from_dump(dump_data, occurence)
        self.update_cpu_mem_tiers()

    def get_vmwrapper(self):
        return self.slicevmdata

    def get_hostwrapper(self):
        return self.slicenodedata

    def get_cpu_mem_tiers(self):
        return self.cpu_tier0, self.cpu_tier1, self.cpu_tier2, self.mem_tier0, self.mem_tier1, self.mem_tier2

    def update_cpu_mem_tiers(self):
        cpu_config, mem_config = self.get_host_config()
        if (cpu_config is None) or (mem_config is None):
            #print("Not enough data to compute cpu/mem tier on this slice: [" + str(self.leftBound) + ";" + str(self.rightBound) + "[")
            return
        
        (slice_cpu_tier0, slice_cpu_tier1) = (None, None)
        (slice_mem_tier0, slice_mem_tier1) = (None, None)

        # Oversubscription strategies based on node usage
        if self.strategy in ['percentile', 'doa', 'greedy', 'nsigma', 'borg', 'maxpeak']:
            nodecomputation = None
            if self.strategy == 'percentile':
                nodecomputation = PercentileOversubscriptionComputation(cpu_percentile=self.model_cpu_percentile,mem_percentile=self.model_mem_percentile)
            elif self.strategy == 'doa':
                nodecomputation = DoaOversubscriptionComputation()
            elif self.strategy == 'greedy':
                nodecomputation = GreedyOversubscriptionComputation(cpu_percentile=self.model_cpu_percentile,mem_percentile=self.model_mem_percentile)
            elif (self.strategy == 'nsigma') or (self.strategy == 'maxpeak'):
                nodecomputation = NSigmaOversubscriptionComputation(N=5)
            elif self.strategy == 'borg':
                nodecomputation = BorgDefaultOversubscriptionComputation(oversubscription_ratio=1.1)
            else:
                raise ValueError("Unknown slice oversubscription mechanism")

            slice_cpu_tier0, slice_cpu_tier1,\
            slice_mem_tier0, slice_mem_tier1 = self.slicenodedata.get_cpu_mem_tiers(nodecomputation)

        # Oversubscription strategies based on VM sum
        if self.strategy in ['rclike', 'maxpeak']:
            vmcomputation = None
            if (self.strategy == 'rclike') or (self.strategy == 'maxpeak'):
                vmcomputation = RClikeOversubscriptionComputation(cpu_percentile=99,mem_percentile=100)
            else:
                raise ValueError("Unknown slice oversubscription mechanism")

            vmcomputation.set_context(object_wrapper_list=list(self.slicevmdata.values()))
            if self.strategy == 'maxpeak': # Specific case, take the most pessimistic approach between two predictors
                tier0_rcl, tier1_rcl = vmcomputation.compute_cpu_tiers()
                if tier0_rcl > slice_cpu_tier0:
                    (slice_cpu_tier0, slice_cpu_tier1) = tier0_rcl, tier1_rcl
                tier0_rcl, tier1_rcl = vmcomputation.compute_mem_tiers()
                if tier0_rcl > slice_mem_tier0:
                    (slice_mem_tier0, slice_mem_tier1) = tier0_rcl, tier1_rcl
            else:
                slice_cpu_tier0, slice_cpu_tier1 = vmcomputation.compute_cpu_tiers()
                slice_mem_tier0, slice_mem_tier1 = vmcomputation.compute_mem_tiers()

        # Fallback
        if (slice_cpu_tier0 == None):
            raise ValueError("Unknown slice oversubscription mechanism")
       
        # Convert quantities to threshold 
        self.convert_cpu_mem_tiers(slice_cpu_tier0=slice_cpu_tier0, slice_cpu_tier1=slice_cpu_tier1, cpu_config=cpu_config, 
                    slice_mem_tier0=slice_mem_tier0, slice_mem_tier1=slice_mem_tier1, mem_config=mem_config)

    # At the slice level, we compute tiers as quantities instead of threshold (TODO : change name?)
    def convert_cpu_mem_tiers(self, slice_cpu_tier0 : int, slice_cpu_tier1 : int, cpu_config : int, slice_mem_tier0 : int, slice_mem_tier1 : int, mem_config : int):
        # Compute CPU tiers quantities from threshold
        self.cpu_tier0 = round(slice_cpu_tier0, 1)
        self.cpu_tier1 = round(slice_cpu_tier1 - self.cpu_tier0, 1)
        if self.cpu_tier1 <= 0:
            self.cpu_tier1 = 0
        if self.cpu_tier1>cpu_config:
            self.cpu_tier1 = cpu_config-self.cpu_tier0
            self.cpu_tier2 = 0
        else:
            self.cpu_tier2 = round(cpu_config - self.cpu_tier1 - self.cpu_tier0, 1)
            if self.cpu_tier2<0:
                self.cpu_tier2=0

        # Compute memory tiers quantities from threshold
        self.mem_tier0 = int(slice_mem_tier0)
        self.mem_tier1 = int(slice_mem_tier1 - self.mem_tier0)
        if self.mem_tier1 < 0:
            self.mem_tier1 = 0
        if self.mem_tier1>mem_config:
            self.mem_tier1 = mem_config-self.mem_tier0
            self.mem_tier2 = 0
        else:
            self.mem_tier2 = int(mem_config - self.mem_tier1 - self.mem_tier0)
            if self.mem_tier2<0:
                self.mem_tier2=0
        
    def retrieve_domain_data(self, begin_epoch : int, end_epoch : int):
        myurl = os.getenv('INFLUXDB_URL')
        mytoken = os.getenv('INFLUXDB_TOKEN')
        myorg = os.getenv('INFLUXDB_ORG')
        mybucket = os.getenv('INFLUXDB_BUCKET')

        client = InfluxDBClient(url=myurl, token=mytoken, org=myorg)
        query_api = client.query_api()
        query = ' from(bucket:"' + mybucket + '")\
        |> range(start: ' + str(begin_epoch) + ', stop: ' + str(end_epoch) + ')\
        |> filter(fn: (r) => r["_measurement"] == "domain")\
        |> filter(fn: (r) => r["url"] == "' + self.model_node_name + '")'

        result = query_api.query(org=myorg, query=query)
        domains_data = defaultdict(lambda: defaultdict(list))

        for table in result:
            for record in table.records:
                domain_name = record.__getitem__('domain')
                timestamp = (record.get_time()).timestamp()
                if timestamp not in domains_data[domain_name]["time"]:
                    domains_data[domain_name]["time"].append(timestamp)
                domains_data[domain_name][record.get_field()].append(record.get_value())
        return domains_data

    def retrieve_node_data(self, begin_epoch : int, end_epoch : int):
        myurl = os.getenv('INFLUXDB_URL')
        mytoken = os.getenv('INFLUXDB_TOKEN')
        myorg = os.getenv('INFLUXDB_ORG')
        mybucket = os.getenv('INFLUXDB_BUCKET')

        client = InfluxDBClient(url=myurl, token=mytoken, org=myorg)
        query_api = client.query_api()
        query = ' from(bucket:"' + mybucket + '")\
        |> range(start: ' + str(begin_epoch) + ', stop: ' + str(end_epoch) + ')\
        |> filter(fn:(r) => r._measurement == "node")\
        |> filter(fn: (r) => r["url"] == "' + self.model_node_name + '")'

        result = query_api.query(org=myorg, query=query)

        node_data = defaultdict(list)

        for table in result:
            for record in table.records:
                timestamp = (record.get_time()).timestamp()
                if timestamp not in node_data["time"]:
                    node_data["time"].append(timestamp)
                node_data[record.get_field()].append(record.get_value())
        return node_data

    def get_host_config(self):
        return self.slicenodedata.get_host_config()

    def get_bound_as_str(self):
        return str(self.leftBound) + ";" + str(self.rightBound) + "["

    def get_vm_cpu_tiers_sum(self):
        slice_cpu_tier0, slice_cpu_tier1 = 0, 0
        slice_mem_tier0, slice_mem_tier1 = 0, 0
        for vmwrapper in self.slicevmdata.values():
            wp_cpu_min, wp_cpu_max, wp_mem_min, wp_mem_max = vmwrapper.get_cpu_mem_tiers()
            slice_cpu_tier0 += wp_cpu_min if wp_cpu_min is not None else 0
            slice_cpu_tier1 += wp_cpu_max if wp_cpu_max is not None else 0
            slice_mem_tier0 += wp_mem_min if wp_mem_min is not None else 0
            slice_mem_tier1 += wp_mem_max if wp_mem_max is not None else 0
        return slice_cpu_tier0, slice_cpu_tier1, slice_mem_tier0, slice_mem_tier1

    def __str__(self):
        slice_cpu_tier0, slice_cpu_tier1, slice_mem_tier0, slice_mem_tier1 = self.get_vm_cpu_tiers_sum()
        txt = "SliceModel[" + str(self.leftBound) + ";" + str(self.rightBound) + "[:" + \
            " cumul cpu min/max " + str(round(slice_cpu_tier0,1)) + "/" + str(round(slice_cpu_tier1,1)) +\
            " cumul mem min/max " + str(round(slice_mem_tier0,1)) + "/" + str(round(slice_mem_tier1,1)) +\
            "\n    >{" + str(self.slicenodedata) + "}"
        # for vm, slicevm in self.slicevmdata.items():
        #     txt += "\n    >{" + str(slicevm) + "}"
        return txt