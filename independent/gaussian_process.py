'''
Created on Mar 9, 2015

@author: ckomurlu
'''

from utils.readdata import convert_time_window_df_randomvar_hour, DATA_DIR_PATH
from utils.node import Neighborhood
from models.ml_reg_model import MLRegModel
import utils.properties
from utils.toolkit import standard_error
from data.humidity_data_preprocess import HumidityProcessor

import numpy as np
from sklearn.gaussian_process import GaussianProcess
from sklearn.metrics import mean_absolute_error, mean_squared_error
from time import time
import cPickle as cpk
import os


class GaussianProcessLocal(MLRegModel):
    def __init__(self):
        super(GaussianProcessLocal, self).__init__()
        self.gpmat = object()

    def fit(self, train_mat, load=False, **kwargs):
        self.sortedids = range(train_mat.shape[0])
        if load:
            tempgp = cpk.load(open(DATA_DIR_PATH + 'gaussianProcessLocal.pkl', 'rb'))
            self.gpmat = tempgp.gpmat
            self.rvCount = self.gpmat.shape[0]
        else:
            Xtrain = np.vectorize(lambda x: x.local_feature_vector)(train_mat)
            ytrain = np.vectorize(lambda x: x.true_label)(train_mat)

            ytrain_split = np.split(ytrain, 3, axis=1)  # Intel data
            # ytrain_split = np.split(ytrain, 31, axis=1)  #Wunderground data
            ytrain_split_array = np.array(ytrain_split)
            ytrain_mean = np.mean(ytrain_split_array, axis=0)

            self.rvCount = Xtrain.shape[0]
            self.gpmat = np.empty(shape=(self.rvCount,), dtype=np.object_)
            for row in range(self.rvCount):
                # self.gpmat[row] = GaussianProcess(corr='cubic', theta0=1e-2, thetaL=1e-4, thetaU=1e-1,
                #                                   random_start=100)
                self.gpmat[row] = GaussianProcess(corr='linear', theta0=1e-2, thetaL=1e-4, thetaU=1e-1,
                                                           random_start=100)
                self.gpmat[row].fit(Xtrain[row, :12].reshape(-1, 1), ytrain_mean[row])  # Intel data
                # self.gpmat[row].fit(Xtrain[row, :4].reshape(-1, 1), ytrain_mean[row])  # Wunderground data

    def computeVar(self, evidMat):
        raise NotImplementedError
        T = evidMat.shape[1]
        varMat = np.zeros(shape=(self.rvCount, T))
        for rv in range(self.rvCount):
            for t in range(T):
                self.gpmat[rvid].predict


    def predict(self, test_mat, evid_mat, **kwargs):
        Xtest = np.vectorize(lambda x: x.local_feature_vector)(test_mat)
        ytest = np.vectorize(lambda x: x.true_label)(test_mat)
        ymeanpred = np.empty(shape=ytest.shape, dtype=ytest.dtype)
        yvarpred = np.empty(shape=ytest.shape, dtype=ytest.dtype)
        for rvid in range(self.rvCount):
            if evid_mat[rvid, -1]:
                ymeanpred[rvid, -1] = ytest[rvid, -1]
                yvarpred[rvid, -1] = 0
            else:
                ymeanpred[rvid, -1], yvarpred[rvid, -1] = self.gpmat[rvid].predict(Xtest[rvid, -1].reshape(-1, 1),
                                                                                   eval_MSE = True)
        return ymeanpred, yvarpred

    def compute_accuracy(self, Y_test, Y_pred):
        raise NotImplementedError

    def compute_confusion_matrix(self, Y_test, Y_pred):
        raise NotImplementedError

    @staticmethod
    def run():
        start = time()
        #         neighborhood_def = Neighborhood.all_others_current_time
        #         trainset,testset = convert_time_window_df_randomvar_hour(True,
        #                                                                 neighborhood_def)
        trainset, testset = convert_time_window_df_randomvar_hour(True,
                                                                  Neighborhood.itself_previous_others_current)

        testset = testset[:, 35:47]
        gp = GaussianProcessLocal()
        gp.fit(trainset, load=True)

        evid_mat = np.zeros(shape=testset.shape, dtype=np.bool_)

        ypred = gp.predict(testset, evid_mat)

        print gp.compute_mean_squared_error(testset, ypred)
        print gp.compute_mean_absolute_error(testset, ypred)

        #         print mean_absolute_error(ytest, ypred)
        #         print mean_squared_error(ytest, ypred)

        end = time()
        print 'Process ended, duration:', end - start

    @staticmethod
    def runActiveInference():
        start = time()
        randomState = np.random.RandomState(seed=0)
        numTrials = utils.properties.numTrials
        T = utils.properties.timeSpan
        trainset, testset = convert_time_window_df_randomvar_hour(True,
                                                                  Neighborhood.itself_previous_others_current)
        # hp = HumidityProcessor()
        # trainset2, testset2 = hp.convert_time_window_df_randomvar_hour(True,
        #                                 Neighborhood.itself_previous_others_current)
        # trainset = np.append(trainset1, trainset2, axis=0)
        # testset = np.append(testset1, testset2, axis=0)
        gp = GaussianProcessLocal()
        gp.fit(trainset, load=False)
        for obsrate in utils.properties.obsrateList:
            obsCount = obsrate * gp.rvCount
            errResults = np.empty(shape=(numTrials, T, 6))
            predResults = np.empty(shape=(numTrials, gp.rvCount, T))
            selectMat = np.empty(shape=(T, obsCount), dtype=np.int16)
            evidencepath = utils.properties.outputDirPath + str(obsrate) + '/evidences/'
            if not os.path.exists(evidencepath):
                os.makedirs(evidencepath)
            predictionpath = utils.properties.outputDirPath + str(obsrate) + '/predictions/'
            if not os.path.exists(predictionpath):
                os.makedirs(predictionpath)
            errorpath = utils.properties.outputDirPath + str(obsrate) + '/errors/'
            if not os.path.exists(errorpath):
                os.makedirs(errorpath)
            print 'obsrate: {}'.format(obsrate)
            print 'trial:'
            for trial in range(numTrials):
                print trial
                evidMat = np.zeros(shape=(gp.rvCount, T), dtype=np.bool_)
                print '\ttime:'
                for t in range(T):
                    print '\t', t
                    select = np.arange(gp.rvCount)
                    randomState.shuffle(select)
                    selectMat[t] = select[:obsCount]
                    evidMat[select[:obsCount], t] = True
                    ypred = gp.predict(testset[:, t], evidMat[:, t])
                    predResults[trial, :, t] = ypred
                    errResults[trial, t, 0] = gp.compute_mean_absolute_error(testset[:, t], ypred,
                                                                             type_=0, evidence_mat=evidMat[:, t])
                    errResults[trial, t, 1] = gp.compute_mean_squared_error(testset[:, t], ypred,
                                                                            type_=0, evidence_mat=evidMat[:, t])
                    errResults[trial, t, 2] = gp.compute_mean_absolute_error(testset[:, t], ypred,
                                                                             type_=1, evidence_mat=evidMat[:, t])
                    errResults[trial, t, 3] = gp.compute_mean_squared_error(testset[:, t], ypred,
                                                                            type_=1, evidence_mat=evidMat[:, t])
                    errResults[trial, t, 4] = gp.compute_mean_absolute_error(testset[:, t], ypred,
                                                                             type_=2, evidence_mat=evidMat[:, t])
                    errResults[trial, t, 5] = gp.compute_mean_squared_error(testset[:, t], ypred,
                                                                            type_=2, evidence_mat=evidMat[:, t])
                np.savetxt(evidencepath +
                           'evidMat_trial={}_obsrate={}.csv'.format(trial, obsrate),
                           evidMat, delimiter=',')
                np.savetxt(predictionpath +
                           'predResults_activeInf_gaussianProcess_T={}_obsRate={}_{}_trial={}.csv'.
                           format(T, obsrate, utils.properties.timeStamp, trial),
                           predResults[trial], delimiter=',')
                np.savetxt(errorpath +
                           'result_activeInf_gaussianProcess_T={}_obsRate={}_{}_trial={}.csv'.
                           format(T, obsrate, utils.properties.timeStamp, trial),
                           errResults[trial], delimiter=',')
            np.savetxt(errorpath +
                       'meanMAE_activeInf_gaussianProcess_T={}_obsRate={}_trial={}.csv'.
                       format(T, obsrate, 'mean'),
                       np.mean(errResults, axis=0), delimiter=',')
            np.savetxt(errorpath +
                       'stderrMAE_activeInf_gaussianProcess_T={}_obsRate={}_trial={}.csv'.
                       format(T, obsrate, 'mean'),
                       standard_error(errResults, axis=0), delimiter=',')
        print 'End of process, duration: {} secs'.format(time() - start)
