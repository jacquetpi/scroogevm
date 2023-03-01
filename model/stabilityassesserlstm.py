import numpy as np
import pandas as pd
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.layers import LSTM
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error
import matplotlib
from matplotlib import pyplot as plt
matplotlib.rcParams['pdf.fonttype'] = 42
pd.set_option('styler.latex.hrules', True)
pd.set_option('styler.format.precision', 2)


class StabilityAssesserLstm(object):

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

    def assess(self, traindata_as_list : list, targetdata : dict, metric : str, max_value_config : int):

        traindata = self.transform_list_of_dict(traindata_as_list, metric, max_value_config)
        projectiondata_time, projectiondata_metrics = self.transform_dict(targetdata, metric, max_value_config)

        tf.random.set_seed(0) # for reproductilibity

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
        model.add(LSTM(6, input_shape=(1, look_back)))
        model.add(Dense(1))
        model.compile(loss='mean_squared_error', optimizer='adam')
        model.fit(trainX, trainY, epochs=3, batch_size=1, verbose=0)

        # make predictions
        trainPredict = model.predict(trainX)
        projectionPredict = model.predict(projectionX)

        # invert predictions
        trainPredict = self.inverse_transform_x(trainPredict, max_value_config)
        trainY = self.inverse_transform_y(trainY, max_value_config)
        projectionPredict = self.inverse_transform_x(projectionPredict, max_value_config)
        projectionY = self.inverse_transform_y(projectionY, max_value_config)

        # calculate root mean squared error
        trainScore = np.sqrt(mean_squared_error(trainY[0], trainPredict[:,0]))
        print('Train Score: %.2f RMSE' % (trainScore))
        projectionScore = np.sqrt(mean_squared_error(projectionY[0], projectionPredict[:,0]))
        print('Projection Score: %.2f RMSE' % (projectionScore))
        
        abs_gap = np.abs(trainScore - projectionScore)
        threshold = max_value_config*0.001
        if abs_gap < threshold:
            print("Considered stable", abs_gap, "<", threshold, "from config", max_value_config)
            is_stable = True
        else:
            print("Considered unstable", abs_gap, ">=", threshold, "from config", max_value_config)
            is_stable = False

        # shift predictions for plotting
        if False:
            trainPredictPlot = np.empty_like(dataset)
            trainPredictPlot[:, :] = np.nan
            trainPredictPlot[look_back:len(trainPredict)+look_back, :] = trainPredict
            # shift test predictions for plotting
            projectionPredictPlot = np.empty_like(dataset)
            projectionPredictPlot[:, :] = np.nan
            projectionPredictPlot[len(trainPredict)+(look_back*2)+1:len(dataset)-1, :] = projectionPredict
            # plot baseline and predictions
            plt.plot(self.inverse_transform_x(dataset, max_value_config))
            plt.plot(trainPredictPlot)
            plt.plot(projectionPredictPlot)
            plt.xlabel('Ticks')
            plt.ylabel('Active cores')
            plt.gcf().savefig('last_graph' + metric + '.pdf', bbox_inches='tight')
            #plt.show()
            plt.cla()
            plt.clf()

        return is_stable
        