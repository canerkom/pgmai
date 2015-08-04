'''
Created on May 13, 2015

@author: ckomurlu
'''
# PATH_TO_PGMAI = 'C:/Users/ckomurlu/git/pgmai'
# import os
# import sys
# sys.path.append(os.path.abspath(PATH_TO_PGMAI))
from utils import readdata
from utils.node import Neighborhood
from utils.readdata import convert_time_window_df_randomvar_hour
from joint.gaussian_DBN import GaussianDBN
from utils.metropolis_hastings import MetropolisHastings
import utils.properties

import numpy as np
import cPickle
from time import time
from scipy.stats import norm
import sys

def forwardSampling(ids, cpdParams, parentDict, sampleSize = 100):    
    sampleStorage = dict()
    for curid in ids:
        sampleStorage[curid] = np.empty(shape = (sampleSize,), dtype=np.float64)
    for currentSample in xrange(sampleSize):
    #     print currentSample
        for currentid in ids:
            try:
                (b0,b,var) = cpdParams[currentid]
                parents = parentDict[currentid]
            except KeyError:
                parents = []
            if parents == []:
                currentmean = b0
            else:
                parentValues = list()
                for parent in parents:
                    parentValues.append(sampleStorage[parent][currentSample])
                parentValues = np.array(parentValues)
                currentmean = b0 + np.dot(b,parentValues)
            sampleStorage[currentid][currentSample] = \
                np.random.normal(currentmean,var**.5)
    return sampleStorage

def convertArcsToGraphInv(arrowlist):
    graph = dict()
    for edge in arrowlist:
        if edge[1] not in graph:
            graph[edge[1]] = list()
        graph[edge[1]].append(edge[0])
    return graph

def computeCondGauss(sensid, parentDict, mea, cova, initial=False):
    try:
        parents = parentDict[sensid]
    except KeyError:
        return mea[sensid],0,cova[sensid,sensid]
    if initial == True:
        parents = parents[:-1]
        if parents == []:
            return mea[sensid],0,cova[sensid,sensid]
    firstInd = np.tile(tuple(parents),len(parents))
    secondInd = np.repeat(tuple(parents),len(parents))
    YY = cova[sensid,sensid]
    YX = cova[sensid,tuple(parents)]
    XY = cova[tuple(parents),sensid]
    XXinv = np.linalg.inv(cova[firstInd,secondInd].reshape(len(parents),
                                                           len(parents)))
    b0 = mea[sensid] - np.dot(np.dot(YX, XXinv), mea[list(parents)])
    b = np.dot(XXinv,YX)
    sigsq = YY - np.dot(np.dot(YX,XXinv),XY.reshape(-1,1))
    return b0,b,sigsq[0]

# np.random.seed(10)
# 
# trainset,testset = readdata.convert_time_window_df_randomvar_hour(True,
#                         Neighborhood.all_others_current_time)
# X = np.vectorize(lambda x: x.true_label)(trainset)
# mea = np.mean(X,axis=1)
# cova = np.cov(X)
# Y = np.append(X[:,1:],X[:,:-1],axis=0)
# cova100 = np.cov(Y)
# mea100 = np.append(mea,mea)
# ids = [17, 21, 18, 20]
# arclist = list()
# for i in xrange(3):
#     arclist.append((ids[i],ids[i+1]))
# arclist.append((17,20))
# arclist.append((21,20))
# parentDict = convertArcsToGraphInv(arclist)
# cpdParams = dict()
# for curid in ids:
#     cpdParams[curid] = computeCondGauss(curid,parentDict,mea100,cova100,initial=False)
# sampleSto = forwardSampling(ids, cpdParams, parentDict)
# for curid in ids:
#     print sampleSto[curid].mean(), mea[curid], sampleSto[curid].var(), cova[curid,curid]

def testAcyclicity():
    start = time()
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.itself_previous_others_current)
#                             Neighborhood.all_others_current_time)
    gdbn = GaussianDBN()
    gdbn.fit(trainset, topology='mst_enriched')
    childDict = gdbn.getChildDict()
    startidx = 2
    grey = set([startidx])
    black = list()
    while grey:
        cur = grey.pop()
        black.append(cur)
        childSet = set([x for x in childDict[cur] if x < gdbn.rvCount])
        blackSet = set(black)
        if blackSet & childSet:
            raise ValueError('Child is already explored, black set child set intersection:' + str(blackSet & childSet))
        grey |= childSet
#         indicesInCol = np.where(np.array(colList) == cur)
#         children = rowList[indicesInCol[0]]
#         rowList = np.delete(rowList,indicesInCol[0])
#         colList = np.delete(colList,indicesInCol[0])
#         for child in children:
#             self.parentDict[child].append(cur)
#         grey += children.tolist()
#     pass

def test():
    np.random.seed(42)
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.all_others_current_time)
    gdbn = GaussianDBN()
    gdbn.fit(trainset)
    numSlice = 6
    result = np.empty(shape=(100,12),dtype=np.float64)
    for i in range(6):
        evidMap = np.zeros((len(gdbn.sortedids),numSlice),dtype=np.bool_)
        evidMap[1,i] = True
    #     evidMap[15,3] = True
        (sampleStorage,weightList, logWeightList) = gdbn.likelihoodWeighting(evidMap, trainset, sampleSize = 100)
        result[:,2*i] = weightList
        result[:,2*i+1] = logWeightList
    for row in result:
        for col in row:
            print col,
        print
    return

def testPredictTrial():
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.all_others_current_time)
    gdbn = GaussianDBN()
    gdbn.fit(trainset)
    Y_pred = gdbn.predict_trial(testset)
    return

def testPredict():
    np.random.seed(17)
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.all_others_current_time)
    gdbn = GaussianDBN()
    gdbn.fit(trainset)
    (sensorCount,testTimeCount) = testset.shape
    numTrial = 10
#     rateList = np.arange(0.0,1.1,0.1)
    rateList = [0.001, 0.01]
    resultMat = np.empty((numTrial,len(rateList),6))
    for currentTrial in xrange(numTrial):
        rateInd = 0
        for evidRate in rateList:
            evidMat = np.random.rand(sensorCount,testTimeCount) < evidRate
#             Y_pred = gdbn.predict(testset,evidMat)
            Y_pred = gdbn.predictTrial(testset,evidMat)
#             Y_true = np.vectorize(lambda x: x.true_label)(testset)
            resultMat[currentTrial,rateInd,0] = gdbn.compute_mean_squared_error(test_set=testset,
                                                                                 Y_pred=Y_pred, type_=0, evidence_mat=evidMat)
            resultMat[currentTrial,rateInd,1] = gdbn.compute_mean_squared_error(test_set=testset,
                                                                                 Y_pred=Y_pred, type_=1, evidence_mat=evidMat)
            resultMat[currentTrial,rateInd,2] = gdbn.compute_mean_squared_error(test_set=testset,
                                                                                 Y_pred=Y_pred, type_=2, evidence_mat=evidMat)
            resultMat[currentTrial,rateInd,3] = gdbn.compute_mean_absolute_error(test_set=testset,
                                                                                 Y_pred=Y_pred, type_=0, evidence_mat=evidMat)
            resultMat[currentTrial,rateInd,4] = gdbn.compute_mean_absolute_error(test_set=testset,
                                                                                 Y_pred=Y_pred, type_=1, evidence_mat=evidMat)
            resultMat[currentTrial,rateInd,5] = gdbn.compute_mean_absolute_error(test_set=testset,
                                                                                 Y_pred=Y_pred, type_=2, evidence_mat=evidMat)
            rateInd += 1
    np.savetxt('C:/Users/ckomurlu/Documents/workbench/experiments/20150528/GDBN_RandomSamplingWrtRates.txt',
               np.mean(resultMat,axis=0),delimiter=',',fmt='%.4f')

def stupidTest():
    np.random.seed(17)
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.all_others_current_time)
    gdbn = GaussianDBN()
    gdbn.fit(trainset)
    evidMat = np.zeros((50,10),dtype=np.bool_)
    (sampleStorage,weightList, logWeightList) = \
                gdbn.likelihoodWeighting(evidMat, testset, sampleSize = 10)
    numSlice = 10
    muMat = np.empty((50,10),dtype=np.float64)
    varMat = np.empty((50,10),dtype=np.float64)
    probDenMat = np.empty((50,10),dtype=np.float64)
    for id_ in gdbn.sortedids:
        parents = gdbn.parentDict[id_][:-1]
        cpdParams = gdbn.cpdParams[id_,0]
        try:
            mu = cpdParams[0] + np.dot(cpdParams[1].T,sampleStorage[0,parents,0])
        except AttributeError:
            mu = cpdParams[0]
        var = cpdParams[2]
        rv = norm(loc=mu,scale=var**.5)
        muMat[id_,0] = mu
        varMat[id_,0] = var
        probDenMat[id_,0] = rv.pdf(testset[id_,0].true_label)
    for t in xrange(1,numSlice):
        for id_ in gdbn.sortedids:
            parentsT = gdbn.parentDict[id_][:-1]
            parentsVals = np.append(sampleStorage[0,parentsT,t],
                                    sampleStorage[0,id_,t-1])
            cpdParams = gdbn.cpdParams[id_,1]
            mu = cpdParams[0] + np.dot(cpdParams[1].T,parentsVals)
            var = cpdParams[2]
            rv = norm(loc=mu,scale=var**.5)
            muMat[id_,t] = mu
            varMat[id_,t] = var
            probDenMat[id_,t] = rv.pdf(testset[id_,0].true_label)

def testMH():
    start = time()
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.itself_previous_others_current)
#                             Neighborhood.all_others_current_time)
    gdbn = GaussianDBN()
    gdbn.fit(trainset)
    parentDict = gdbn.parentDict
    rvids = np.array(parentDict.keys())
    rvCount = int(rvids.shape[0])
    T = 10
    evidMat = np.zeros((rvCount,T),dtype=np.bool_)
    evidMat[2,0] = True
    testMat = np.zeros((rvCount,T),dtype=np.float_)
    testMat[2,0] = 25.0
    
    
    sampleSize = 2000
    burnInCount = 1000
    samplingPeriod = 2
    width = float(sys.argv[1])
    
    startupVals = np.ones((rvCount,T),dtype=np.float_)*20
    
    metropolisHastings = MetropolisHastings()
    (data,accList,propVals,accCount) = metropolisHastings.sampleTemporal(gdbn.sortedids,
                                            parentDict, gdbn.cpdParams, startupVals, evidMat,
                                            testMat, sampleSize=sampleSize,
                                            burnInCount=burnInCount, samplingPeriod=samplingPeriod,
                                            proposalDist='uniform', width=width)
    cPickle.dump((data,accList,propVals,accCount), open(readdata.DATA_DIR_PATH + 'mhResultsEvid1weight='+
                                                        str(width)+'.pkl','wb'))
    
    print 'Process Ended in ', time() - start
    
def testMH3():
    start = time()
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.itself_previous_others_current)
#                             Neighborhood.all_others_current_time)
    gdbn = GaussianDBN()
    gdbn.fit(trainset, topology='mst')
    parentDict = gdbn.parentDict
    rvids = np.array(parentDict.keys())
    rvCount = int(rvids.shape[0])
    T = 1
    evidMat = np.zeros((rvCount,T),dtype=np.bool_)
    evidMat[2,0] = True
    testMat = np.zeros((rvCount,T),dtype=np.float_)
    testMat[2,0] = 25.0
    
    
    sampleSize = 9000
    burnInCount = 1000
    samplingPeriod = 2
    #width for the original topology
    width = [0.4,0.3,0.3,0.4,0.2,0.3,0.2,0.3,0.3,0.8,0.8,1.6,1,0.9,0.4,0.5,0.4,0.5,0.6,0.3,0.4,1.1,
             0.3,0.3,0.3,0.3,0.3,0.3,0.4,0.8,0.9,0.7,0.9,0.3,0.7,0.7,0.4,0.4,0.6,0.4,1.2,0.5,0.5,1,
             0.6,1.5,1.4,1.5,0.5,0.5]
    
    startupVals = np.ones((rvCount,T),dtype=np.float_)*20
    
    metropolisHastings = MetropolisHastings()
    (data,accList,propVals,accCount) = metropolisHastings.sampleTemporal(gdbn.sortedids,
                                            parentDict, gdbn.cpdParams, startupVals, evidMat,
                                            testMat, sampleSize=sampleSize,
                                            burnInCount=burnInCount, samplingPeriod=samplingPeriod,
                                            proposalDist='uniform', width=width)
    cPickle.dump((data,accList,propVals,accCount), open(readdata.DATA_DIR_PATH +
                                                        'mhResultsEvid1weightAdj_9k_mst.pkl','wb'))
    
    print 'Process Ended in ', time() - start
    
def testMH4():
    start = time()
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.itself_previous_others_current)
#                             Neighborhood.all_others_current_time)
    gdbn = GaussianDBN()
    gdbn.fit(trainset)
    parentDict = gdbn.parentDict
    rvids = np.array(parentDict.keys())
    rvCount = int(rvids.shape[0])
    T = 12
    evidMat = np.zeros((rvCount,T),dtype=np.bool_)
    evidMat[:,0] = True
    testMat = np.zeros((rvCount,T),dtype=np.float_)
    Y = np.vectorize(lambda x: x.true_label)(testset)
#     testMat[:,0] = Y[:,8]
    testMat[:,0] = 25.0
    
    
    sampleSize = 10000
    burnInCount = 2000
    samplingPeriod = 2
    width = [0.4,0.3,0.3,0.4,0.2,0.3,0.2,0.3,0.3,0.8,0.8,1.6,1,0.9,0.4,0.5,0.4,0.5,0.6,0.3,0.4,1.1,
             0.3,0.3,0.3,0.3,0.3,0.3,0.4,0.8,0.9,0.7,0.9,0.3,0.7,0.7,0.4,0.4,0.6,0.4,1.2,0.5,0.5,1,
             0.6,1.5,1.4,1.5,0.5,0.5]
    
    startupVals = np.ones((rvCount,T),dtype=np.float_)*20
    
    metropolisHastings = MetropolisHastings()
    (data,accList,propVals,accCount) = metropolisHastings.sampleTemporal(gdbn.sortedids,
                                            parentDict, gdbn.cpdParams, startupVals, evidMat,
                                            testMat, sampleSize=sampleSize,
                                            burnInCount=burnInCount, samplingPeriod=samplingPeriod,
                                            proposalDist='uniform', width=width)
    cPickle.dump((data,accList,propVals,accCount), open(readdata.DATA_DIR_PATH +
                                                        'mhResultsEvid1weightAdj_MST2.pkl','wb'))
    
    print 'Process Ended in ', time() - start
    
def testMH6():
    start = time()
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.itself_previous_others_current)
#                             Neighborhood.all_others_current_time)
    gdbn = GaussianDBN()
    gdbn.fit(trainset)
    parentDict = gdbn.parentDict
    rvids = np.array(parentDict.keys())
    rvCount = int(rvids.shape[0])
    T = 12
    evidMat = np.zeros((rvCount,T),dtype=np.bool_)
    evidMat[:,0] = True
    testMat = np.zeros((rvCount,T),dtype=np.float_)
    Y = np.vectorize(lambda x: x.true_label)(testset)
#     testMat[:,0] = Y[:,8]
    testMat[:,0] = 25.0
    
    
    sampleSize = 120000
    burnInCount = 20000
    samplingPeriod = 1
    width = [0.7,0.4,0.5,1,0.6,0.7,0.4,0.4,0.6,0.8,0.9,1.5,1.6,2.4,1.8,1.6,2.1,1.3,1.5,1.3,
             2.1,2,0.5,0.5,0.7,0.9,1.4,1.4,1.7,0.9,1.2,1.1,1.5,1,1.7,1.3,1.2,0.7,1.3,0.9,2,
             1.8,1.8,2,1.3,1.6,2.3,1.7,1,0.8]
    
    startupVals = np.ones((rvCount,T),dtype=np.float_)*20
    
    metropolisHastings = MetropolisHastings()
    (data,accList,propVals,accCount) = metropolisHastings.sampleTemporal(gdbn.sortedids,
                                            parentDict, gdbn.cpdParams, startupVals, evidMat,
                                            testMat, sampleSize=sampleSize,
                                            burnInCount=burnInCount, samplingPeriod=samplingPeriod,
                                            proposalDist='uniform', width=width)
    cPickle.dump((data,accList,propVals,accCount), open(readdata.DATA_DIR_PATH +
                                                        'mhResultsEvid1widthAdjusted_MST5.pkl','wb'))
    
    print 'Process Ended in ', time() - start
    
def testMH7():
    start = time()
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.itself_previous_others_current)
#                             Neighborhood.all_others_current_time)
    gdbn = GaussianDBN()
    gdbn.fit(trainset, topology='mst')
    parentDict = gdbn.parentDict
    rvids = np.array(parentDict.keys())
    rvCount = int(rvids.shape[0])
    T = 1
    evidMat = np.zeros((rvCount,T),dtype=np.bool_)
    evidMat[2,0] = True
    testMat = np.zeros((rvCount,T),dtype=np.float_)
    Y = np.vectorize(lambda x: x.true_label)(testset)
#     testMat[:,0] = Y[:,8]
    testMat[2,0] = 25.0
    
    sampleSize = 9000
    burnInCount = 5
    samplingPeriod = 1
#     width = [0.7,0.4,0.5,1,0.6,0.7,0.4,0.4,0.6,0.8,0.9,1.5,1.6,2.6,2,1.7,2.3,1.3,1.5,1.3,2.2,2.1,0.5,
#              0.5,0.7,0.9,1.4,1.4,1.8,0.9,1.2,1.1,1.5,1,1.8,1.3,1.2,0.7,1.3,0.9,2.2,1.9,1.9,2.1,1.3,
#              1.6,2.5,1.9,1,0.8]
    width = [0.7,0.4,0.5,1,0.6,0.7,0.4,0.4,0.6,0.8,0.9,1.5,1.6,2.4,1.8,1.6,2.1,1.3,1.5,1.3,
             2.1,2,0.5,0.5,0.7,0.9,1.4,1.4,1.7,0.9,1.2,1.1,1.5,1,1.7,1.3,1.2,0.7,1.3,0.9,2,
             1.8,1.8,2,1.3,1.6,2.3,1.7,1,0.8]
    
    startupVals = np.ones((rvCount,T),dtype=np.float_)*20
    
    metropolisHastings = MetropolisHastings()
    (data,accList,propVals,accCount) = metropolisHastings.sampleTemporal(gdbn.sortedids,
                                            parentDict, gdbn.cpdParams, startupVals, evidMat,
                                            testMat, sampleSize=sampleSize,
                                            burnInCount=burnInCount, samplingPeriod=samplingPeriod,
                                            proposalDist='uniform', width=width)
    cPickle.dump((data,accList,propVals,accCount), open(readdata.DATA_DIR_PATH +
                                            'mhResultsEvid1weightAdj_9k_mst3.pkl','wb'))
    
    print 'Process Ended in ', time() - start

def testActiveInferenceGaussianDBN():
    randomState = np.random.RandomState(seed=0)
    tWin = 6
    observationRate = .1
    topology = 'mst'
    T=12
    
    start = time()
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.itself_previous_others_current)
    gdbn = GaussianDBN()
    gdbn.fit(trainset, topology=topology)
    obsCount = observationRate * gdbn.rvCount
    Y_test_allT = np.vectorize(lambda x: x.true_label)(testset)
#     T = Y_test_allT.shape[1]
    evidMat = np.zeros(shape=testset.shape,dtype=np.bool_)
    results = np.empty(shape=(T,2))
    selectMat = np.empty(shape=(T,obsCount),dtype=np.int16)
    sensormeans = cPickle.load(open(readdata.DATA_DIR_PATH + 'sensormeans.pkl','rb'))
    print 'time:'
    for t in range(T):
        print t
        select = np.arange(gdbn.rvCount)
        randomState.shuffle(select)
        selectMat[t] = select[:obsCount]
        evidMat[select[:obsCount],t] = True
        if t < tWin:
            Y_test = Y_test_allT[:,:t+1]
            testMat = testset[:,:t+1]
            curEvidMat = evidMat[:,:t+1]
        else:
            Y_test = Y_test_allT[:,t+1-tWin:t+1]
            testMat = testset[:,t+1-tWin:t+1]
            curEvidMat = evidMat[:,t+1-tWin:t+1]
        startupVals = np.repeat(sensormeans.reshape(-1,1),Y_test.shape[1],axis=1)
        Y_pred = gdbn.predict(Y_test,curEvidMat, t, sampleSize=20,startupVals=startupVals)
        results[t,0] = gdbn.compute_mean_absolute_error(testMat[:,-1], Y_pred[:,-1], type_=2,
                                                        evidence_mat=curEvidMat[:,-1])
        results[t,1] = gdbn.compute_mean_squared_error(testMat[:,-1], Y_pred[:,-1], type_=2,
                                                       evidence_mat=curEvidMat[:,-1])
#     np.savetxt(utils.properties.outputDirPath+'selectedSensorsObsRate{}.csv'.format(
#             observationRate), selectMat, delimiter=',')
    cPickle.dump(results, open(utils.properties.outputDirPath+'result_activeInf_gaussianDBN_'+
                               'topology={}_window={}_T={}_obsRate={}_{}.pkl'.format(topology,tWin,T,
                                observationRate,utils.properties.timeStamp),'wb'), protocol=0)
    print 'End of process, duration(sec): ', time()-start

testActiveInferenceGaussianDBN()

def testMH5():
    start = time()
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.itself_previous_others_current)
#                             Neighborhood.all_others_current_time)
    gdbn = GaussianDBN()
    gdbn.fit(trainset)
    parentDict = gdbn.parentDict
    rvids = np.array(parentDict.keys())
    rvCount = int(rvids.shape[0])
    T = 12
    evidMat = np.zeros((rvCount,T),dtype=np.bool_)
    evidMat[:,0] = True
    testMat = np.zeros((rvCount,T),dtype=np.float_)
    Y = np.vectorize(lambda x: x.true_label)(testset)
#     testMat[:,0] = Y[:,8]
    testMat[:,0] = 25.0
    
    result = np.empty(shape = (50,16))
    
    sampleSize = 2000
    burnInCount = 1000
    samplingPeriod = 2
    count = 0
    for width in np.arange(1.7,2.6,0.1):
        print count
        startupVals = np.ones((rvCount,T),dtype=np.float_)*20
        metropolisHastings = MetropolisHastings()
        (data,accList,propVals,accCount) = metropolisHastings.sampleTemporal(gdbn.sortedids,
                                            parentDict, gdbn.cpdParams, startupVals, evidMat,
                                            testMat, sampleSize=sampleSize,
                                            burnInCount=burnInCount, samplingPeriod=samplingPeriod,
                                            proposalDist='uniform', width=width)
        result[:,count] = np.mean(1 - accCount / 2000,axis=1)
        count += 1
    cPickle.dump(result, open(readdata.DATA_DIR_PATH + 'mhResultsEvid1weightBenchmark_MST3.pkl','wb'))
    
    print 'Process Ended in ', time() - start

def testForwardSampling():
    start = time()
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.itself_previous_others_current)
#                             Neighborhood.all_others_current_time)
    gdbn = GaussianDBN()
    gdbn.fit(trainset, topology='mst')
    rvCount = len(gdbn.sortedids)
    T = 1
    evidMat = np.zeros((rvCount,T),dtype=np.bool_)
    evidMat[2,0] = True
    testMat = np.zeros((rvCount,T),dtype=np.float_)
    Y = np.vectorize(lambda x: x.true_label)(testset)
#     testMat[:,0] = Y[:,8]
    testMat[2,0] = 25.0
    
    sampleSize = 4000
    
    sampleStorage = gdbn.forwardSampling(evidMat, testMat, sampleSize, T)
    cPickle.dump(sampleStorage,open(readdata.DATA_DIR_PATH + 'forwardSamplingGDBN_mst_4k.pkl','wb'))
    print 'Process ended in: ', time() - start
    
def testMH2():
    start = time()
    parentDict = {0:[3],1:[0,4],2:[1,5]}
    cpdParams = np.empty(shape=(3,2),dtype=tuple)
    cpdParams[0,0] = (21.7211,np.array([]),5.79045)
    cpdParams[1,0] = (-1.43977,np.array([1.04446]),0.638121)
    cpdParams[2,0] = (-1.58985,np.array([1.0515]),0.871026)
    cpdParams[0,1] = (0.90683765,np.array([0.95825092]),0.41825906)
    cpdParams[1,1] = (-1.17329,np.array([0.49933,0.544751]),0.278563)
    cpdParams[2,1] = (-0.902438,np.array([0.410928,0.622744]),0.390682)
    rvids = np.array(parentDict.keys())
    rvCount = int(rvids.shape[0])
    T = 1
    evidMat = np.zeros((rvCount,T),dtype=bool)
    testMat = np.zeros((rvCount,T))
    sampleSize = 2000
    burnInCount = 1000
    samplingPeriod = 2
    width = 0.3
    startupVals = np.array([[20., 20., 20., 20.],
                            [20., 20., 20., 20.],
                            [20., 20., 20., 20.]])
    metropolisHastings = MetropolisHastings()
    (data,accList,propVals,accCount) = metropolisHastings.sampleTemporal(rvids,
                                            parentDict, cpdParams, startupVals, evidMat,
                                            testMat, sampleSize=sampleSize,
                                            burnInCount=burnInCount, samplingPeriod=samplingPeriod,
                                            proposalDist='uniform', width=width)
    cPickle.dump((data,accList,propVals,accCount), open(readdata.DATA_DIR_PATH + 'mhResultsEvidDnm12.pkl','wb'))
    
    print 'Process Ended in ', time() - start

# testAcyclicity()
# testMH7()
# testForwardSampling()

# stupidTest()
# testPredict()


########################
####### Garbage ########
########################

#     def checkTopoSort(self):
#         parentSet = dict()
#         for i in self.parentDict:
#             parentSet[i] = set(self.parentDict[i])
#         toposorted = list(toposort(parentSet))
#         followIndex = 0
#         for item in self.sortedids:
#             for i in xrange(followIndex,len(toposorted)):
#                 if item in toposorted[i]:
#                     followIndex = i
#                     break
#             else:
#                 raise ValueError('sortedids list is not topologically sorted.'+str(item)+
#                                  ' could not be found in the remaining topological sets' +
#                                  ' following index:', followIndex)
# 
#     @staticmethod
#     def checkTopoSortA(sortedids,parentDict):
#         toposorted = list(toposort(parentDict))
#         followIndex = 0
#         for item in sortedids:
#             for i in xrange(followIndex,len(toposorted)):
#                 if item in toposorted[i]:
#                     followIndex = i
#                     break
#             else:
#                 raise ValueError('sortedids list is not topologically sorted.'+str(item)+
#                                  ' could not be found in the remaining topological sets' +
#                                  ' following index:', followIndex)
# 
# def testCheckTopoSort():
# #     ts = list(toposort({2: {11},
# #                 9: {11, 8, 10},
# #                 10: {11, 3},
# #                 11: {7, 5},
# #                 8: {7, 3},
# #                }))
#     parentDict = {2: {11},
#                 9: {11, 8, 10},
#                 10: {11, 3},
#                 11: {7, 5},
#                 8: {7, 3},
#                }
#     tsf = toposort_flatten({2: {11},
#                 9: {11, 8, 10},
#                 10: {11, 3},
#                 11: {7, 5},
#                 8: {7, 3},
#                })
#     
#     GaussianDBN.checkTopoSortA(tsf[::-1], parentDict)