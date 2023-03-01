from model.sliceobject import SliceObject

class SliceHost(SliceObject):

    def __init__(self, slice_object : SliceObject, vm_list : list, booked_cpu : int, booked_mem):
        # Retrieve parent attribute for computation
        slice_attributes = slice_object.__dict__
        slice_attributes["compute"] = True
        super().__init__(**slice_attributes)
        # Specific attributes
        self.vm_list=vm_list
        self.booked_cpu=booked_cpu
        self.booked_mem=booked_mem
        self.cpu_stable_state=False
        self.mem_stable_state=False

    def get_vm_list(self):
        return self.vm_list

    def is_vm_in(self, vm : str):
        return (vm in self.vm_list)

    def __str__(self):
        return "SliceHost[" +  str(round(self.cpu_avg,1))  + "/" + str(round(self.get_cpu_percentile(90))) + "/" + str(int(self.cpu_config)) + " " +\
            str(round(self.mem_avg,1))  + "/" + str(round(self.get_mem_percentile(90))) + "/" + str(int(self.mem_config)) + " " +\
            "alert_oc_cpu=" + str(self.alert_oc_cpu()) + " alert_oc_mem=" + str(self.alert_oc_mem()) + "]"

    def alert_oc_cpu(self):
        return (self.oc_sched_wait>1000); # TODO value

    def alert_oc_mem(self):
        return (self.oc_page_fault>100000); # TODO value

    def set_cpu_stability(self, stable : bool):
        self.stable_state=stable

    def set_stability(self, cpu_stability : bool, mem_stability : bool):
        self.cpu_stable_state=cpu_stability
        self.mem_stable_state=mem_stability

    def is_cpu_stable(self):
        return self.cpu_stable_state

    def is_mem_stable(self):
        return self.mem_stable_state

    def get_booked_cpu(self):
        return self.booked_cpu

    def get_booked_mem(self):
        return self.booked_mem

    def dump_state_to_dict(self, dump_dict : dict, iteration : int = 0):
        for attribute, value in self.__dict__.items():
            if attribute not in dump_dict:
                if attribute in ["raw_data", "cpu_percentile", "mem_percentile", "cpi", "hwcpucycles"]:
                    dump_dict[attribute] = [dict() for x in range(iteration)] # in case of new host
                elif attribute in ["vm_list"]:
                    dump_dict[attribute] = [list() for x in range(iteration)]
                else:
                     dump_dict[attribute] = [0 for x in range(iteration)]
            dump_dict[attribute].append(value)

    def __str__(self):
        return "SliceHost[" +  str(self.cpu_avg)  + "/" + str(round(self.get_cpu_percentile(90))) + "/" + str(self.cpu_config) + " " +\
            str(self.mem_avg)  + "/" + str(round(self.get_mem_percentile(90)))  + "/" + str(self.mem_config) + " " +\
            "cpu_stable_state=" + str(self.cpu_stable_state) + " mem_stable_state=" + str(self.mem_stable_state) + "]"