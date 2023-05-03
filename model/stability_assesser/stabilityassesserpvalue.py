from model.sliceobject import SliceObject
import numpy as np
from scipy.stats import ttest_ind_from_stats

class StabilityAssesserPValue(object):

    instance_count = 1  # Static

    def __init__(self):
        self.id = StabilityAssesserPValue.instance_count 
        StabilityAssesserPValue.instance_count+=1

    # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind_from_stats.html
    def assess(self, old_data : list, new_data : list, threshold : int = 0.1):
        old_average = np.average(old_data)
        old_std = np.std(old_data)
        new_average =  np.average(new_data)
        new_std =  np.std(new_data)
        stats, pvalue = ttest_ind_from_stats(old_average, old_std, len(old_data), new_average, new_std, len(new_data))
        # identical list return nan, nan which is evaluated as false
        return pvalue < threshold

    def assess_from_slice(self, last_slice : SliceObject, new_slice : SliceObject, metric, threshold : int = 0.1):
        old_data = last_slice.get_raw_metric(metric=metric)
        new_data = new_slice.get_raw_metric(metric=metric)
        return self.assess(old_data=old_data, new_data=new_data, threshold=threshold)