import numpy as np
import math
from model.sliceobjectwrapper import SliceObjectWrapper

# Abstract class
class OversubscriptionComputation(object):

    def __init__(self, object_wrapper : SliceObjectWrapper):
        self.object_wrapper = object_wrapper 

    def update_cpu_tiers(self, cpu_tier0 : int, cpu_tier1 : int):
        studied_slice = self.object_wrapper.get_last_slice()
        studied_slice.update_cpu_tiers(cpu_tier0, cpu_tier1)
        return cpu_tier0, cpu_tier1

    def update_mem_tiers(self, mem_tier0 : int, mem_tier1 : int):
        studied_slice = self.object_wrapper.get_last_slice()
        studied_slice.update_mem_tiers(mem_tier0, mem_tier1)
        return mem_tier0, mem_tier1

    # Misc functions
    def round_to_upper_nearest(self, x : int, nearest_val : int):
        return nearest_val * math.ceil(x/nearest_val)

class DoaOversubscriptionComputation(OversubscriptionComputation):

    def __init__(self, object_wrapper : SliceObjectWrapper):
        super().__init__(object_wrapper=object_wrapper)
        self.increase_ratio = 20 # increase by 5%
        self.treshold = 0.95
        self.decrease_ratio = 2 # decrease by 20%
        self.max_ratio = 3 # Due to implementation, max OC is not bounded in a non "scheduler linked" env

    def __compute_generic_tiers(self, value : str, previous_tier0 : int, config_resources : int):
        applied_threshold = config_resources*self.treshold
        if value < applied_threshold:
            # To increase oversubscribtion value, we diminue the "seen as used" quantity
            generic_tier0 = previous_tier0 - round(config_resources/self.increase_ratio)
            min_value = (-(self.max_ratio-1)*config_resources) # negative, min used value of ratio 2 for a 256 core config is -256
            if generic_tier0 < min_value: # 
                generic_tier0 = min_value
        else:
            # To decrease oversubscribtion value, we increase the "seen as used" quantity
            generic_tier0 =  previous_tier0 + round(config_resources/self.decrease_ratio)
        
        return generic_tier0, generic_tier0 # No Tier1 in this paper

    def compute_cpu_tiers(self):
        studied_slice = self.object_wrapper.get_last_slice()
        previous_slice = self.object_wrapper.get_nth_to_last_slice(1)
        if previous_slice is None :
            init_value = studied_slice.get_booked_cpu() # Init at 1:1
            previous_cpu_tier0, previous_cpu_tier1 = (init_value, init_value)
        else:
            previous_cpu_tier0, previous_cpu_tier1 = previous_slice.get_cpu_tiers()
        cpu_config = studied_slice.get_cpu_config()
        max_value = studied_slice.get_cpu_max()
        cpu_tier0, cpu_tier1 = self.__compute_generic_tiers(value=max_value,previous_tier0=previous_cpu_tier0,config_resources=cpu_config)
        return super().update_cpu_tiers(cpu_tier0, cpu_tier1)

    def compute_mem_tiers(self):
        studied_slice = self.object_wrapper.get_last_slice()
        previous_slice = self.object_wrapper.get_nth_to_last_slice(1)
        if previous_slice is None :
            init_value = studied_slice.get_booked_mem()# Init at 1:1
            previous_mem_tier0, previous_mem_tier1 = (init_value, init_value)
        else:
            previous_mem_tier0, previous_mem_tier1 = previous_slice.get_mem_tiers()
        mem_config = studied_slice.get_mem_config()
        max_value = studied_slice.get_mem_max()
        cpu_tier0, cpu_tier1 = self.__compute_generic_tiers(value=max_value,previous_tier0=previous_mem_tier0,config_resources=mem_config)
        return super().update_mem_tiers(cpu_tier0, cpu_tier1)

class PercentileOversubscriptionComputation(OversubscriptionComputation):

    def __init__(self, object_wrapper : SliceObjectWrapper, cpu_percentile : int, mem_percentile : int):
        super().__init__(object_wrapper=object_wrapper)
        self.cpu_percentile = cpu_percentile
        self.mem_percentile = mem_percentile

    def __compute_generic_tiers(self, metric : str, percentile : int):
        values = self.object_wrapper.get_slices_raw_metric(metric)
        generic_tier0 = np.percentile(values, percentile)
        return generic_tier0, generic_tier0 # No Tier1 in this paper

    def compute_cpu_tiers(self):
        cpu_tier0, cpu_tier1 = self.__compute_generic_tiers(metric='cpu_usage', percentile=self.cpu_percentile)
        return super().update_cpu_tiers(cpu_tier0, cpu_tier1)

    def compute_mem_tiers(self):
        mem_tier0, mem_tier1 = self.__compute_generic_tiers(metric='mem_usage', percentile=self.mem_percentile)
        return super().update_mem_tiers(mem_tier0, mem_tier1)

class GreedyOversubscriptionComputation(OversubscriptionComputation):

    def __init__(self, object_wrapper : SliceObjectWrapper, cpu_percentile : int, mem_percentile : int):
        super().__init__(object_wrapper=object_wrapper)
        self.cpu_percentile = cpu_percentile
        self.mem_percentile = mem_percentile

    def __compute_generic_tiers(self, is_stable : bool, max_percentile : int, booked_resources : int, 
                                previous_tier0 : int, previous_tier1 : int, previous_booked : int):

        if is_stable:
            generic_tier0 = max_percentile
        else:
            generic_tier0 = booked_resources

            if previous_tier0 is not None:

                generic_tier0, generic_tier1 = (previous_tier0, previous_tier1)

                delta_provision = booked_resources - previous_booked
                delta_usage = max_percentile - generic_tier0

                is_provisioning_increasing = (delta_provision > 0)
                is_usage_increasing = (delta_usage > 0)
                
                # If usage is decreasing : we just wait for quiescent state
                # If usage is increasing : we have to be more reactive
                if is_usage_increasing:

                    generic_tier0 += max(delta_usage, delta_provision)

        generic_tier1 = generic_tier0 # No Tier1 in this paper
        return generic_tier0, generic_tier1
        
    # CPU tiers as threshold
    def compute_cpu_tiers(self):
        # Retrieve current slice intel
        studied_slice = self.object_wrapper.get_last_slice()
        max_percentile = self.round_to_upper_nearest(x=self.object_wrapper.get_slices_max_metric(cpu_percentile=self.cpu_percentile), nearest_val=0.1)
        booked_cpu = studied_slice.get_booked_cpu()
        is_stable = studied_slice.is_cpu_stable()
        # Retrieve last slice intel
        previous_slice = self.object_wrapper.get_nth_to_last_slice(1)
        previous_cpu_tier0, previous_cpu_tier1, previous_cpu_booked = (None, None, None)
        if previous_slice is not None :
            previous_cpu_tier0, previous_cpu_tier1 = previous_slice.get_cpu_tiers()
            previous_cpu_booked = previous_slice.get_booked_cpu()
        # Compute tiers
        cpu_tier0, cpu_tier1 = self.__compute_generic_tiers(is_stable=is_stable, max_percentile=max_percentile, booked_resources=booked_cpu, 
                                                    previous_tier0=previous_cpu_tier0, previous_tier1=previous_cpu_tier1, previous_booked=previous_cpu_booked)
        return super().update_cpu_tiers(cpu_tier0, cpu_tier1)

    # Mem tiers as threshold
    def compute_mem_tiers(self):
        # Retrieve current slice intel
        studied_slice = self.object_wrapper.get_last_slice()
        max_percentile = self.round_to_upper_nearest(x=self.object_wrapper.get_slices_max_metric(mem_percentile=self.mem_percentile), nearest_val=1)
        booked_mem = studied_slice.get_booked_mem()
        is_stable = studied_slice.is_mem_stable()
        # Retrieve last slice intel
        previous_slice = self.object_wrapper.get_nth_to_last_slice(1)
        previous_mem_tier0, previous_mem_tier1, previous_mem_booked = (None, None, None)
        if previous_slice is not None :
            previous_mem_tier0, previous_mem_tier1 = previous_slice.get_mem_tiers()
            previous_mem_booked = previous_slice.get_booked_mem()
        # Compute tiers
        mem_tier0, mem_tier1 = self.__compute_generic_tiers(is_stable=is_stable, max_percentile=max_percentile, booked_resources=booked_mem, 
                                                    previous_tier0=previous_mem_tier0, previous_tier1=previous_mem_tier1, previous_booked=previous_mem_booked)
        return super().update_mem_tiers(mem_tier0, mem_tier1)