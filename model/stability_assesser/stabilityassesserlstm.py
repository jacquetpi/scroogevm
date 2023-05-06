import numpy as np
import pandas as pd
import os
import json
from model.sliceobject import SliceObject
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.layers import LSTM
from numpy.random import seed
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error
import matplotlib
from matplotlib import pyplot as plt
matplotlib.rcParams['pdf.fonttype'] = 42
pd.set_option('styler.latex.hrules', True)
pd.set_option('styler.format.precision', 2)


class StabilityAssesserLstm(object):

    instance_count = 1  # Static

    def __init__(self):
        self.id = StabilityAssesserLstm.instance_count
        StabilityAssesserLstm.instance_count+=1

    def assess(self, old_data : list, new_data : list, max_config = None, threshold : int = 0.01, debug : bool =False):
        if max_config == None:
            max_config = max([max(old_data), max(new_data)])

        time_list = list(range(len(old_data) + len(new_data)))

        new_data_list = dict()
        new_data_list['time'] = time_list[:len(old_data)]
        new_data_list['metric'] = [float(x) for x in old_data]

        current_data = list()
        x = dict()
        x['time'] = time_list[len(old_data):]
        x['metric'] = [float(x) for x in new_data]
        current_data.append(x)
        
        return self.__internal_assess(traindata_as_list=current_data, targetdata=new_data_list, metric='metric', max_value_config=max_config, threshold=threshold, debug=debug)

    def assess_form_slice_list(self, slice_list : list, new_slice : SliceObject, metric : str, max_config : int):
        current_data = list()
        index=0
        for slice in slice_list:
            x = dict()
            x["time"] = slice.get_raw_metric("time")
            x[metric] = slice.get_raw_metric(metric)
            current_data.append(x)
            index+=1

        new_data = dict()
        new_data["time"] = [x for x in new_slice.get_raw_metric("time")]
        new_data[metric] = new_slice.get_raw_metric(metric)

        return self.__internal_assess(traindata_as_list=current_data, targetdata=new_data, metric=metric, max_value_config=max_config)

    def transform_list_of_dict(self, traindata_as_list : dict, metric : str, max_value_config : int):
        traindata = dict()
        traindata["time"] = list()
        traindata[metric] = list()
        for slicedata in traindata_as_list:
            time, metrics = self.transform_dict(slicedata, metric, max_value_config)
            traindata["time"].extend(time)
            traindata[metric].extend(metrics)
        return traindata

    def transform_dict(self, slicedata : dict, metric : str, max_value_config):
        return slicedata["time"], [round(x/max_value_config,3) for x in slicedata[metric]]

    def inverse_transform_x(self,  array : np.array, max_value_config : int):
        reverse_array = [round(x[0]*max_value_config,1) for x in array]
        return np.array(reverse_array)[..., np.newaxis]

    def inverse_transform_y(self,  array : np.array, max_value_config : int):
        reverse_array = [round(x*max_value_config,1) for x in array]
        return np.array([reverse_array])

    # convert an array of values into a dataset matrix
    def create_dataset(self, dataset, look_back=1):
        dataX, dataY = [], []
        for i in range(len(dataset)-look_back-1):
            a = dataset[i:(i+look_back), 0]
            dataX.append(a)
            dataY.append(dataset[i + look_back, 0])
        return np.array(dataX), np.array(dataY)

    def __internal_assess(self, traindata_as_list : list, targetdata : dict, metric : str, max_value_config : int, threshold : int = 0.01, debug=True):

        traindata = self.transform_list_of_dict(traindata_as_list, metric, max_value_config)
        projectiondata_time, projectiondata_metrics = self.transform_dict(targetdata, metric, max_value_config)

        # for reproductilibity
        seed(0)
        tf.random.set_seed(1) 
        tf.keras.utils.set_random_seed(2)
        tf.config.experimental.enable_op_determinism()

        dataset = np.array(traindata[metric] + projectiondata_metrics)[..., np.newaxis] # for plotting purpose only
        dataset_train = np.array(traindata[metric])[..., np.newaxis]
        dataset_projection = np.array(projectiondata_metrics)[..., np.newaxis]

        look_back = 1
        trainX, trainY = self.create_dataset(dataset_train, look_back)
        projectionX, projectionY =  self.create_dataset(dataset_projection, look_back)

        # reshape input to be [samples, time steps, features]
        trainX = np.reshape(trainX, (trainX.shape[0], 1, trainX.shape[1]))
        projectionX = np.reshape(projectionX, (projectionX.shape[0], 1, projectionX.shape[1]))

        # create and fit the LSTM network
        model = Sequential()
        model.add(LSTM(4, input_shape=(1, look_back)))
        model.add(Dense(1))
        model.compile(loss='mean_squared_error', optimizer='adam')
        model.fit(trainX, trainY, epochs=3, batch_size=1, verbose=0)

        # make predictions
        trainPredict = model.predict(trainX, verbose=0)
        projectionPredict = model.predict(projectionX, verbose=0)

        # invert predictions
        trainPredict = self.inverse_transform_x(trainPredict, max_value_config)
        trainY = self.inverse_transform_y(trainY, max_value_config)
        projectionPredict = self.inverse_transform_x(projectionPredict, max_value_config)
        projectionY = self.inverse_transform_y(projectionY, max_value_config)

        # calculate root mean squared error
        trainScore = np.sqrt(mean_squared_error(trainY[0], trainPredict[:,0]))
        if debug: print('Train Score: %.2f RMSE' % (trainScore))
        projectionScore = np.sqrt(mean_squared_error(projectionY[0], projectionPredict[:,0]))
        if debug: print('Projection Score: %.2f RMSE' % (projectionScore))
        
        abs_gap = np.abs(trainScore - projectionScore)
        threshold_val = max_value_config*threshold
        if abs_gap < threshold_val:
            if debug: print("Considered stable", abs_gap, "<", threshold_val, "from config", max_value_config)
            is_stable = True
        else:
            if debug: print("Considered unstable", abs_gap, ">=", threshold_val, "from config", max_value_config)
            is_stable = False

        self.dump_debug(dataset=dataset, look_back=look_back, trainPredict=trainPredict, projectionPredict=projectionPredict, 
                        metric=metric, max_value_config=max_value_config, trainScore=trainScore, projectionScore=projectionScore,
                        input_old=traindata_as_list, input_new=targetdata,
                        abs_gap=abs_gap, threshold=threshold_val)

        return is_stable
        
    # convert an array of values into a dataset matrix
    def create_dataset(self, dataset, look_back=1):
        dataX, dataY = [], []
        for i in range(len(dataset)-look_back-1):
            a = dataset[i:(i+look_back), 0]
            dataX.append(a)
            dataY.append(dataset[i + look_back, 0])
        return np.array(dataX), np.array(dataY)

    def dump_debug(self, dataset : pd.DataFrame, look_back : pd.DataFrame, trainPredict : pd.DataFrame, projectionPredict : pd.DataFrame,
                metric : str, max_value_config : int, trainScore : float, projectionScore : float, abs_gap : float, threshold : float,
                input_old : list, input_new : dict):
        
        dump_lstm_file_location = 'dump-lstm.csv'
        if os.path.isfile(dump_lstm_file_location):
            trainPredictPlot = np.empty_like(dataset)
            trainPredictPlot[:, :] = np.nan
            trainPredictPlot[look_back:len(trainPredict)+look_back, :] = trainPredict
            # shift test predictions for plotting
            projectionPredictPlot = np.empty_like(dataset)
            projectionPredictPlot[:, :] = np.nan
            projectionPredictPlot[len(trainPredict)+(look_back*2)+1:len(dataset)-1, :] = projectionPredict
            # plot baseline and predictions
            np_inverse = self.inverse_transform_x(dataset, max_value_config)
            # header = 'iteration,metric,config,trainscore,projectionscore,gap,threshold,realdata,predictold,predictnew'
            separator = '\t'
            with open(dump_lstm_file_location,'a') as fd:
                fd.write(
                    str(self.id) + separator +\
                    str(metric) + separator +\
                    str(max_value_config) + separator +\
                    str(trainScore) + separator +\
                    str(projectionScore) + separator +\
                    str(abs_gap) + separator +\
                    str(threshold) + separator +\
                    self.convert_to_hex( ''.join(str(x) for x in np_inverse)) + separator +\
                    self.convert_to_hex( ''.join(str(x) for x in trainPredictPlot)) + separator +\
                    self.convert_to_hex( ''.join(str(x) for x in projectionPredictPlot)) + separator +\
                    self.convert_to_hex(json.dumps(input_old)) + separator +\
                    self.convert_to_hex(json.dumps(input_new)) +'\n'
                )

    def convert_to_hex(self, string : str):
        return string.encode("utf-8").hex()