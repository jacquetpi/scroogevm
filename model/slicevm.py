from model.sliceobject import SliceObject

class SliceVm(SliceObject):

    def __init__(self, slice_object : SliceObject):
        # Retrieve parent attribute for computation
        slice_attributes = slice_object.__dict__
        slice_attributes["compute"] = True
        super().__init__(**slice_attributes)
        # Specific attributes
        self.cpu_state = 0
        self.mem_state = 0

    def update_state(self, cpu_state : int, mem_state : int):
        # Check cpu_state validity
        if cpu_state < 0:
            self.cpu_state = 0
        elif cpu_state > 2:
            self.cpu_state = 2
        else:
            self.cpu_state = cpu_state
        # Check mem_state validity
        if mem_state < 0:
            self.mem_state = 0
        elif mem_state > 2:
            self.mem_state = 2
        else:
            self.mem_state = mem_state

    def get_cpu_state(self):
        return self.cpu_state
    
    def get_mem_state(self):
        return self.mem_state

    def __eq__(self, other) : 
        if other == None:
            return False
        if self.cpu_avg != other.cpu_avg:
            return False
        if self.cpu_std != other.cpu_std:
            return False
        if self.mem_avg != other.mem_avg:
            return False
        if self.oc_page_fault != other.oc_page_fault:
            return False
        if self.oc_sched_wait != other.oc_sched_wait:
            return False
        if self.number_of_values != other.number_of_values:
            return False
        return True

    def dump_state_to_dict(self, dump_dict : dict, iteration : int = 0):
        for attribute, value in self.__dict__.items():
            if attribute not in dump_dict:
                if attribute in ["raw_data", "cpu_percentile", "mem_percentile", "cpi", "hwcpucycles"]:
                    dump_dict[attribute] = [dict() for x in range(iteration)] # in case of a new VM
                else:
                    dump_dict[attribute] = [0 for x in range(iteration)]
            dump_dict[attribute].append(value)

    def __str__(self):
        return "SliceVM[" +  str(self.cpu_avg)  + "/" + str(round(self.get_cpu_percentile(90))) + "/" + str(self.cpu_config) + " " +\
            str(self.mem_avg)  + "/" + str(round(self.get_mem_percentile(90)))  + "/" + str(self.mem_config) + " " +\
            "cpu_state=" + str(self.cpu_state) + " mem_state=" + str(self.mem_state) + "]"