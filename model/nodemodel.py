from model.slicemodel import SliceModel
from model.sliceobject import SliceObject
from model.slicevm import SliceVm
import time
import pandas as pd
import matplotlib.pyplot as plt

class NodeModel(object):

    def __init__(self, node_name : str, model_scope : int, slice_scope, historical_occurences : int, 
                    cpu_percentile : int, mem_percentile : int, strategy : str, aggregation : int):
        if slice_scope > model_scope:
            raise ValueError("Model scope must be greater than slice scope")
        if model_scope % slice_scope !=0:
            raise ValueError("Model scope must be a slice multiple")
        self.node_name=node_name
        self.node_scope=model_scope
        self.slice_scope=slice_scope
        self.number_of_slice=int(model_scope/slice_scope)
        self.historical_occurences=historical_occurences
        self.init_epoch=int(time.time())
        self.slices = list()
        self.aggregation = aggregation
        for i in range(self.number_of_slice):
            self.slices.append(SliceModel(
                model_node_name= node_name, model_position=i, model_init_epoch=self.init_epoch, model_historical_occurences=historical_occurences, 
                model_number_of_slice=self.number_of_slice, leftBound=i*slice_scope, rightBound=(i+1)*slice_scope,
                cpu_percentile=cpu_percentile, mem_percentile=mem_percentile, strategy=strategy, aggregation=aggregation))

    def build_past_slices_from_epoch(self, past_slice : int):
        for slice in self.slices:
            slice.build_past_slices_from_epoch(past_slice)

    def build_last_slice_from_epoch(self):
        previous_scope_number, previous_slice_number = self.get_previous_scope_and_slice_number()
        self.get_slice(previous_slice_number).build_slice_from_epoch(previous_scope_number)
        return previous_slice_number

    def build_slice_from_dump(self, dump : dict, occurence : int):
        scope_number, slice_number = self.get_scope_and_slice_number_from_occurence(occurence)
        self.get_slice(slice_number).build_slice_from_dump(dump, occurence)
        return slice_number

    def get_current_scope_and_slice_number(self):
        delta = int(time.time()) - self.init_epoch
        scope_number = int(delta / self.node_scope)
        slice_number = int((delta % self.node_scope)/self.slice_scope)
        return scope_number, slice_number

    def get_scope_and_slice_number_from_occurence(self, occurence : int):
        self.number_of_slice
        scope_number = int(occurence / self.number_of_slice)
        slice_number = occurence - (scope_number*self.number_of_slice)
        return scope_number, slice_number 

    def get_previous_scope_and_slice_number(self):
        current_scope, current_slice_number = self.get_current_scope_and_slice_number()
        previous_slice_number = current_slice_number-1
        if previous_slice_number < 0:
            previous_slice_number = (self.number_of_slice-1)
            previous_scope = current_scope-1
            if previous_scope<0:
                raise ValueError("No previous iteration at call")
        else:
            previous_scope = current_scope # no iteration change on last slice
        return previous_scope, previous_slice_number

    def get_slice(self, slice_number):
        return self.slices[slice_number]

    def get_free_cpu_mem(self, slice_number : int = None):
        # If slice number is specified, we return its value
        if slice_number != None:
            cpu_tier0, cpu_tier1, cpu_tier2, mem_tier0, mem_tier1, mem_tier2 = self.get_slice(slice_number).get_cpu_mem_tiers()
            cpu_tier_min_value, mem_tier_min_value = (cpu_tier2, mem_tier2)
        # Otherwise, we return the minimum value observed in scope
        else:
            cpu_tier_min_value, mem_tier_min_value = float('inf'), float('inf')
            for slice in self.slices:
                cpu_tier0, cpu_tier1, cpu_tier2, mem_tier0, mem_tier1, mem_tier2 = slice.get_cpu_mem_tiers()
                print("node debug0", cpu_tier0)
                if cpu_tier2 is None :
                    print("No data were retrieved from this scope on worker node", self.node_name)
                    print("If you are running scroogevm on a live setting. Check the following :")
                    print("> vmprobe is launched on worker node")
                    print("> A prometheus exporter parses vmprobe file endpoint and exposes it to http://localhost:9100/metrics on worker node")
                    print("> vmaggreg.py is launched and configured to retrieve the http endpoint (possibly remotely")
                    raise ValueError("no data from worker")
                if cpu_tier2 < cpu_tier_min_value:
                    cpu_tier_min_value = cpu_tier2
                if mem_tier2 < mem_tier_min_value:
                    mem_tier_min_value = mem_tier2
        if cpu_tier_min_value < 0:
            cpu_tier_min_value = 0 # Possible in an overcommited scenario
        if mem_tier_min_value < 0:
            mem_tier_min_value = 0 # Possible in an overcommited scenario
        return cpu_tier_min_value, mem_tier_min_value

    def __str__(self, slice_number : int = None):
        free_cpu, free_mem = self.get_free_cpu_mem(slice_number)
        txt = "NodeModel{url=" + self.node_name + "} free_cpu=" + str(free_cpu) + " free_mem=" + str(free_mem) + "\n"
        for slice in self.slices:
            txt= txt + "  |_" + str(slice) + "\n"
        return txt

    def display_model(self):
        slices=[]
        groups=[]
        tiers = {"tier0":[], "tier1":[], "tier2":[]}
        for slice in self.slices:
            slices.append(slice.get_bound_as_str())
            groups.append("cpu")
            cpu_tier0, cpu_tier1, cpu_tier2, mem_tier0, mem_tier1, mem_tier2 = slice.get_cpu_mem_tiers()
            tiers["tier0"].append(cpu_tier0)
            tiers["tier1"].append(cpu_tier1)
            tiers["tier2"].append(cpu_tier2)
        for slice in self.slices:
            slices.append(slice.get_bound_as_str())
            groups.append("mem")
            cpu_tier0, cpu_tier1, cpu_tier2, mem_tier0, mem_tier1, mem_tier2 = slice.get_cpu_mem_tiers()
            tiers["tier0"].append(mem_tier0)
            tiers["tier1"].append(mem_tier1)
            tiers["tier2"].append(mem_tier2)

        fig, axes = plt.subplots(1,2,figsize=(18,9))

        df = pd.DataFrame({'groups': groups, 'tier0' : tiers["tier0"], 'tier1' : tiers["tier1"], 'tier2' : tiers["tier2"]}, index=slices)
        for (k,d), ax in zip(df.groupby('groups'), axes.flat):
            axes = d.plot.bar(stacked=True, ax=ax, title=(k + " tiers"))
            axes.legend(loc=2)
        fig.canvas.manager.set_window_title("CPU/Mem tiers on node " + self.node_name)
        plt.show()

    def dump_state_and_slice_to_dict(self, dump_dict : dict, slice_number : int, epoch : int = -1):
        to_dump = ["free_cpu", "free_mem", "cpu_tier0", "cpu_tier1", "cpu_tier2", "mem_tier0", "mem_tier1", "mem_tier2"]
        if "config" not in dump_dict:
            dump_dict["epoch"] = list()
            category = ["config", "node", "vm", "model"]
            for x in category:
                dump_dict[x]=dict()
            for x in to_dump:
                 dump_dict["model"][x]=list()
        dump_dict["config"]["node_scope"] = self.node_scope
        dump_dict["config"]["slice_scope"] = self.slice_scope
        dump_dict["config"]["number_of_slice"] = self.number_of_slice
        dump_dict["config"]["historical_occurences"] = self.historical_occurences
        dump_dict["config"]["node_name"] = self.node_name
        free_cpu, free_mem = self.get_free_cpu_mem(slice_number)
        dump_dict["model"]["free_cpu"].append(free_cpu)
        print("dumped free_cpu", slice_number, ":", dump_dict["model"]["free_cpu"][-1])
        dump_dict["model"]["free_mem"].append(free_mem)
        cpu_tier0, cpu_tier1, cpu_tier2, mem_tier0, mem_tier1, mem_tier2 = self.get_slice(slice_number).get_cpu_mem_tiers()
        dump_dict["model"]["cpu_tier0"].append(cpu_tier0)
        dump_dict["model"]["cpu_tier1"].append(cpu_tier1)
        dump_dict["model"]["cpu_tier2"].append(cpu_tier2)
        dump_dict["model"]["mem_tier0"].append(mem_tier0)
        dump_dict["model"]["mem_tier1"].append(mem_tier1)
        dump_dict["model"]["mem_tier2"].append(mem_tier2)

        self.get_slice(slice_number).get_hostwrapper().get_last_slice().dump_state_to_dict(dump_dict=dump_dict["node"], iteration=len(dump_dict["epoch"]))
        print("dumped percentile", slice_number, ":", dump_dict["node"]["cpu_percentile"][-1][90])
        for vm, vmwrapper in self.get_slice(slice_number).get_vmwrapper().items():
            if vm not in dump_dict["vm"]:
                dump_dict["vm"][vm] = dict()
            last_slice = vmwrapper.get_last_slice()
            if last_slice == None: last_slice = SliceVm(SliceObject(raw_data=dict(), aggregation=self.aggregation))
            last_slice.dump_state_to_dict(dump_dict=dump_dict["vm"][vm], iteration=len(dump_dict["epoch"]))

        if epoch < 0:
            epoch = int(time.time()) - self.init_epoch
        dump_dict["epoch"].append(epoch)

        return dump_dict