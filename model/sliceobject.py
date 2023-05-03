import numpy as np
import sys

class SliceObject(object):

    # Can be build either by passing raw data or by passing all required attributes
    def __init__(self, **kwargs):
        required_attributes = ["cpu_config","mem_config","cpu_percentile","mem_percentile",
        "cpu_avg","mem_avg","cpu_std","mem_std","cpu_max","mem_max",
        "oc_page_fault","oc_page_fault_std","oc_sched_wait","oc_sched_wait_std","cpi","hwcpucycles","number_of_values"]
        self.aggregation = kwargs["aggregation"]
        if "raw_data" in kwargs:
            if ("compute" in kwargs) and (kwargs["compute"]): # avoid dual computation as this object is rebuilt by its childrens
                self.compute_attributes(kwargs["raw_data"])
            self.raw_data = kwargs["raw_data"]
        else:
            for attribute in required_attributes:
                setattr(self, attribute, kwargs[attribute])
        self.cpu_tier0 = None
        self.cpu_tier1 = None
        self.cpu_tier2 = None
        self.mem_tier0 = None
        self.mem_tier1 = None
        self.mem_tier2 = None

    def aggregate(self, data_as_list : list, sum : bool = False):
        if self.aggregation <= 1:
            return data_as_list
        data_aggregated = list()
        for i in range(0, len(data_as_list), self.aggregation):
            chunk = data_as_list[i:i+self.aggregation]
            if sum:
                data_aggregated.append(np.sum(chunk))
            else:
                data_aggregated.append(np.average(chunk))
        if (len(chunk) < self.aggregation) and (len(data_as_list)> self.aggregation): # remove last value if uncomplete
            data_aggregated.pop()
        return data_aggregated

    def compute_attributes(self, raw_data : dict):
        if "mem_rss" in raw_data:
            memory_metric = "mem_rss" # VM case
        else:
            memory_metric = "mem_usage" # host case
        # CPU/mem indicators
        self.cpu_config = raw_data["cpu"][-1] if raw_data.get('cpu', False) else None
        self.mem_config = raw_data["mem"][-1] if raw_data.get('mem', False) else None
        self.cpu_avg = np.average(self.aggregate(raw_data["cpu_usage"])) if raw_data.get('cpu_usage', False) else None
        self.mem_avg = np.average(self.aggregate(raw_data[memory_metric])) if raw_data.get(memory_metric, False) else None
        self.cpu_std = np.std(self.aggregate(raw_data["cpu_usage"])) if raw_data.get('cpu_usage', False) else None
        self.mem_std = np.std(self.aggregate(raw_data[memory_metric])) if raw_data.get(memory_metric, False) else None
        self.cpu_max = np.max(self.aggregate(raw_data["cpu_usage"])) if raw_data.get('cpu_usage', False) else None
        self.mem_max = np.max(self.aggregate(raw_data[memory_metric])) if raw_data.get(memory_metric, False) else None
        # Overcommitment indicators
        self.oc_page_fault = np.percentile(self.aggregate(raw_data['swpagefaults'],sum=True),90) if raw_data.get("swpagefaults", False) else None
        self.oc_page_fault_std = np.std(self.aggregate(raw_data['swpagefaults'],sum=True)) if raw_data.get("swpagefaults", False) else None
        self.oc_sched_wait = np.percentile(self.aggregate(raw_data['sched_busy']),90) if raw_data.get("sched_busy", False) else None
        self.oc_sched_wait_std=np.std(self.aggregate(raw_data['sched_busy'])) if raw_data.get("sched_busy", False) else None
        self.cpi = dict()
        self.hwcpucycles = dict()
        self.cpu_percentile = dict()
        self.mem_percentile = dict()
        if "cpu_usage" in raw_data and raw_data["cpu_usage"]:
            for i in range(10, 90, 5): # percentiles from 10 to 85
                self.cpu_percentile[i] = np.percentile(self.aggregate(raw_data['cpu_usage']),i)
            for i in range(90, 100, 1): # percentiles from 90 to 99
                self.cpu_percentile[i] = np.percentile(self.aggregate(raw_data['cpu_usage']),i)
        if memory_metric in raw_data and raw_data[memory_metric]:
            for i in range(10, 90, 5): # percentiles from 10 to 85
                self.mem_percentile[i] = np.percentile(self.aggregate(raw_data[memory_metric]),i)
            for i in range(90, 100, 1): # percentiles from 90 to 99
                self.mem_percentile[i] = np.percentile(self.aggregate(raw_data[memory_metric]),i)
        if "cpi" in raw_data:
            for i in range(10, 100, 5):
                self.cpi[i] = np.percentile(self.aggregate(raw_data["cpi"]),i)
        if "hwcpucycles" in raw_data:
            for i in range(10, 100, 5):
                self.hwcpucycles[i] = np.percentile(self.aggregate(raw_data["hwcpucycles"]),i)

        self.number_of_values = len(self.aggregate(raw_data['time'])) if 'time' in raw_data else 0

    def get_cpu_config(self):
        return self.cpu_config

    def get_mem_config(self):
        return self.mem_config

    def get_cpu_max(self):
        return self.cpu_max

    def get_mem_max(self):
        return self.mem_max

    def get_cpu_avg(self):
        return self.cpu_avg
    
    def get_mem_avg(self):
        return self.mem_avg

    def get_percentile(self, attribute : str, percentile : int):
        if percentile in getattr(self, attribute):
            return getattr(self, attribute)[percentile]
        if str(percentile) in getattr(self, attribute):    
            return getattr(self, attribute)[str(percentile)]
        return None

    def get_cpu_percentile(self, percentile : int):
        return self.get_percentile('cpu_percentile', percentile)

    def get_mem_percentile(self, percentile : int):
        return self.get_percentile('mem_percentile', percentile)

    def get_cpi_percentile(self, percentile : int):
        return self.get_percentile('cpi', percentile)

    def get_hwcpucycles_percentile(self, percentile : int):
        return self.get_percentile('hwcpucycles', percentile)

    def is_cpu_tier_defined(self):
        if (self.cpu_tier0 is None) or (self.cpu_tier1 is None) or (self.cpu_tier2 is None):
            return False
        return True

    def is_mem_tier_defined(self):
        if (self.mem_tier0 is None) or (self.mem_tier1 is None) or (self.mem_tier2 is None):
            return False
        return True

    def get_cpu_tier0(self):
        return self.cpu_tier0

    def get_cpu_tiers(self):
        return self.cpu_tier0, self.cpu_tier1

    def get_mem_tier0(self):
        return self.mem_tier0

    def get_mem_tiers(self):
        return self.mem_tier0, self.mem_tier1

    def get_mem_tiers(self):
        return self.mem_tier0, self.mem_tier1

    def get_raw_metric(self, metric : str):
        if metric in self.raw_data:
            return self.raw_data[metric]
        else:
            return list()

    # Tiers as threshold
    def update_cpu_tiers(self, cpu_tier0, cpu_tier1):
        # Tiers are computed at the wrapper level to take into account previous slices, but updated here to be able to dump current state
        self.cpu_tier0=cpu_tier0
        self.cpu_tier1=cpu_tier1
        self.cpu_tier2=self.cpu_config

    # Tiers as threshold
    def update_mem_tiers(self, mem_tier0, mem_tier1):
        # Tiers are computed at the wrapper level to take into account previous slices, but updated here to be able to dump current state
        self.mem_tier0=mem_tier0
        self.mem_tier1=mem_tier1
        self.mem_tier2=self.mem_config
