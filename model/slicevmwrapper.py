from model.sliceobjectwrapper import SliceObjectWrapper
from model.sliceobject import SliceObject
from model.slicevm import SliceVm
from scipy.stats import ttest_ind_from_stats

class SliceVmWrapper(SliceObjectWrapper):

    def __init__(self, domain_name : str, historical_occurences : int, cpu_percentile : int, mem_percentile : int, aggregation : int):
        super().__init__(historical_occurences, cpu_percentile, mem_percentile, aggregation)
        self.domain_name=domain_name
        self.debug_cpu_reason = "=0 no prev data"
        self.debug_mem_reason = "=0 no prev data"

    def add_slice_data_from_raw(self, domain_data : dict):
        if(len(domain_data.keys()) == 0):
            print("Empty data on slice encountered on domain " + self.domain_name)
            return
        slice_vm = SliceVm(self.get_slice_object_from_raw(domain_data))
        self.compute_state_of_new_slice(slice_vm)
        self.add_slice(slice_vm)

    def add_slice_data_from_dump(self, vm_dump_data : dict, occurence : int, epoch : int):
        if(len(vm_dump_data.keys()) == 0):
            print("Empty data on slice encountered on dump " + self.domain_name)
            return
        slice_vm = SliceVm(self.get_slice_object_from_dump(dump_data=vm_dump_data, occurence=occurence, epoch=epoch))
        ## Temporary fix
        if slice_vm == self.get_last_slice():
            return False
        ## End of temporary fix
        self.compute_state_of_new_slice(slice_vm)
        self.add_slice(slice_vm)
        return True

    def is_incoherent_value_according_to_pvalue(self, new_slice : SliceVm, metric : str, std_metric : str):
        last_slice = self.get_last_slice()
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind_from_stats.html
        stats, pvalue = ttest_ind_from_stats(
                            getattr(last_slice, metric), getattr(last_slice, std_metric), getattr(last_slice, 'number_of_values'), 
                            getattr(new_slice, metric), getattr(new_slice, std_metric), getattr(new_slice, 'number_of_values'))
        # identical list return nan, nan which is evaluated as false
        return pvalue < 0.1

    def is_incoherent_value(self, new_slice : SliceVm, std_metric : str, metric : str = None, cpu_percentile : int = None, mem_percentile : int = None, multiplier : int = 10):
        last_slice = self.get_last_slice()
        if metric is not None:
            last_value = self.get_slices_max_metric(metric=metric)
            new_value = getattr(new_slice, metric)
        elif cpu_percentile is not None:
            last_value = self.get_slices_max_metric(cpu_percentile=cpu_percentile)
            new_value = new_slice.get_cpu_percentile(cpu_percentile)
        elif mem_percentile is not None:
            last_value = self.get_slices_max_metric(mem_percentile=mem_percentile)
            new_value = new_slice.get_mem_percentile(mem_percentile)
        else:
            raise ValueError("No metrics passed to is_incoherent_value()")
        if (last_value is None) or (new_value is None):
            return True
        variation =  self.get_slices_max_metric(metric=metric,cpu_percentile=cpu_percentile,mem_percentile=mem_percentile)
        threshold = last_value + (multiplier*variation if variation is not None else 0)
        return new_value > threshold

    def compute_cpu_state_of_new_slice(self, new_slice : SliceVm):
        current_cpu_state = self.get_last_slice().get_cpu_state()
        # If config changed
        if (self.get_last_slice().get_cpu_config() != new_slice.cpu_config):
            self.debug_cpu_reason = ">0 conf changed"
            return 0
        # If oc is too important
        if self.is_incoherent_value(new_slice=new_slice, metric='oc_sched_wait', std_metric='oc_sched_wait_std'):
            self.debug_cpu_reason = ">0 perf oc desc"
            return 0
        # If behavior changed
        if self.is_incoherent_value(new_slice=new_slice, metric='cpu_avg', std_metric='cpu_std'):
            self.debug_cpu_reason = "-1 avg increase"
            return current_cpu_state-1
        if self.is_incoherent_value(new_slice=new_slice, cpu_percentile=self.cpu_percentile, std_metric='cpu_std'):
            self.debug_cpu_reason = "-1 nth increase"
            return current_cpu_state-1
        # Stability case
        self.debug_cpu_reason = "+1 usage stable"
        return current_cpu_state+1

    def compute_mem_state_of_new_slice(self, new_slice : SliceVm):
        current_mem_state = self.get_last_slice().get_mem_state()
        # If config changed
        if (self.get_last_slice().get_mem_config() != new_slice.mem_config):
            self.debug_mem_reason = ">0 conf changed"
            return 0
        # If oc is too important
        if self.is_incoherent_value(new_slice=new_slice, metric='oc_page_fault', std_metric='oc_page_fault_std'):
            self.debug_mem_reason = ">0 perf oc desc"
            return 0
        # If behavior changed
        if self.is_incoherent_value(new_slice=new_slice, metric='mem_avg', std_metric='mem_std'):
            self.debug_mem_reason = "-1 avg increase"
            return current_mem_state-1
        if self.is_incoherent_value(new_slice=new_slice, mem_percentile=self.mem_percentile, std_metric='mem_std'):
            self.debug_mem_reason = "-1 nth increase"
            return current_mem_state-1
        # Stability case
        self.debug_mem_reason = "+1 usage stable"
        return current_mem_state+1

    def compute_state_of_new_slice(self, new_slice : SliceVm):
        cpu_state = 0
        mem_state = 0
        if(self.is_historical_full()):
            cpu_state = self.compute_cpu_state_of_new_slice(new_slice)
            mem_state = self.compute_mem_state_of_new_slice(new_slice)
        new_slice.update_state(cpu_state = cpu_state, mem_state = mem_state)

    # VM tiers as threshold
    def get_cpu_tiers(self): # return tier0, tier1
        if self.get_last_slice().is_cpu_tier_defined():
            return self.get_last_slice().get_cpu_tiers()
        # Main algorithm
        cpu_state = self.get_last_slice().get_cpu_state()
        if cpu_state == 0:
            cpu_tier0 = self.get_last_slice().get_cpu_config()
            cpu_tier1 = self.get_last_slice().get_cpu_config()
        elif cpu_state == 1:
            cpu_tier0 = self.round_to_upper_nearest(x=self.get_slices_max_metric(cpu_percentile=95), nearest_val=0.50) # unity is vcpu
            cpu_tier1 = self.get_last_slice().get_cpu_config()
        else:
            cpu_tier0 = self.round_to_upper_nearest(x=self.get_slices_max_metric(metric='cpu_avg'), nearest_val=0.50)
            cpu_tier1 = self.round_to_upper_nearest(x=self.get_slices_max_metric(cpu_percentile=95), nearest_val=0.50)
        self.get_last_slice().update_cpu_tiers(cpu_tier0, cpu_tier1)
        return cpu_tier0, cpu_tier1

    # VM tiers as threshold
    def get_mem_tiers(self): # return tier0, tier1
        if self.get_last_slice().is_mem_tier_defined():
            return self.get_last_slice().get_mem_tiers()
        # Main algorithm
        mem_state = self.get_last_slice().get_mem_state()
        if mem_state == 0:
            mem_tier0 = self.get_last_slice().get_mem_config()
            mem_tier1 = self.get_last_slice().get_mem_config()
        elif mem_state == 1:
            mem_tier0 = self.round_to_upper_nearest(x=self.get_slices_max_metric(mem_percentile=95), nearest_val=256) # unity is MB
            mem_tier1 = self.get_last_slice().get_mem_config()
        else:
            mem_tier0 = self.round_to_upper_nearest(x=self.get_slices_max_metric(metric='mem_avg'), nearest_val=256)
            mem_tier1 = self.round_to_upper_nearest(x=self.get_slices_max_metric(mem_percentile=95), nearest_val=256)
        self.get_last_slice().update_mem_tiers(mem_tier0, mem_tier1)
        return mem_tier0, mem_tier1

    def get_cpu_mem_tiers(self): # return cpu_tier0, cpu_tier1, mem_tier0, mem_tier1
        cpu_tier0, cpu_tier1 = self.get_cpu_tiers()
        mem_tier0, mem_tier1 = self.get_mem_tiers()
        return cpu_tier0, cpu_tier1, mem_tier0, mem_tier1

    def __str__(self):
        if(len(self.slice_object_list)>0):
            cpu_tier0, cpu_tier1, mem_tier0, mem_tier1 = self.get_cpu_mem_tiers()
            cpu_state = self.get_last_slice().get_cpu_state()
            mem_state = self.get_last_slice().get_mem_state()
            return "SliceVmWrapper for " + self.domain_name + ": " +\
                 "cpu_state=" + str(cpu_state) + "(" + self.debug_cpu_reason + ") [" + str(round(cpu_tier0,1)) + ";" + str(round(cpu_tier1,1)) + "] " +\
                 "mem_state=" + str(mem_state) + "(" + self.debug_mem_reason + ") [" + str(round(mem_tier0,1)) + ";" + str(round(mem_tier1,1)) + "]"
        else:
            return "SliceVmWrapper for " + self.domain_name + ": no data"