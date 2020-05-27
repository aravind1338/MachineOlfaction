import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor,ExtraTreesRegressor
from sklearn.model_selection import ShuffleSplit,cross_val_score
from sklearn.linear_model import RandomizedLasso,Ridge

from opc_python import * # Import constants.  
from opc_python.utils import scoring,prog,loading
from opc_python.gerkin import dream

# Use random forest regression to fit the entire training data set, 
# one descriptor set at a time.  
def rfc_final(X,Y_imp,Y_mask,
              max_features,min_samples_leaf,max_depth,et,use_mask,trans_weight,
              trans_params,X_test_int=None,X_test_other=None,Y_test=None,
              n_estimators=100,seed=0,quiet=False):
    
    if X_test_int is None:
        X_test_int = X
    if X_test_other is None:
        X_test_other = X
    if Y_test is None:
        Y_test = Y_mask


    Y_imp = {'mean':Y_imp.mean(axis=1,level=1),
             'std':Y_imp.std(axis=1,level=1)}
    Y_mask = {'mean':Y_mask.mean(axis=1),
              'std':Y_mask.std(axis=1)}
    descriptors = loading.get_descriptors(format=True)

    def rfc_maker(n_estimators=n_estimators,max_features=max_features,
                  min_samples_leaf=min_samples_leaf,max_depth=max_depth,
                  et=False):
        if not et: 
            kls = RandomForestRegressor
            kwargs = {'oob_score':False}
        else:
            kls = ExtraTreesRegressor
            kwargs = {}

        return kls(n_estimators=n_estimators, max_features=max_features,
                   min_samples_leaf=min_samples_leaf, max_depth=max_depth,
                   n_jobs=-1, random_state=seed, **kwargs)
        
    rfcs = {x:{} for x in ('mean','std')}
    for d,descriptor in enumerate(descriptors*2):
        prog(d,2*len(descriptors))
        kind = 'std' if d >= len(descriptors) else 'mean'
        rfcs[kind][descriptor] = rfc_maker(n_estimators=n_estimators,
                                        max_features=max_features[d],
                                        min_samples_leaf=min_samples_leaf[d],
                                        max_depth=max_depth[d],
                                        et=et[d])

        if use_mask[d]:
            rfcs[kind][descriptor].fit(X,Y_mask[kind][descriptor])
        else:
            rfcs[kind][descriptor].fit(X,Y_imp[kind][descriptor])
    
    columns = pd.MultiIndex.from_product([descriptors,('mean','std')],
                                          names=['Descriptor','Moment'])
    predicted = pd.DataFrame(index=X_test_int.index,columns=columns)
    for d,descriptor in enumerate(descriptors*2):
        X_test = X_test_int if descriptor == 'Intensity' else X_test_other
        kind = 'std' if d >= len(descriptors) else 'mean'
        if et[d] or not np.array_equal(X,X_test_int):
            # Possibly check in-sample fit because there isn't any alternative.  
            predicted[(descriptor,kind)] = rfcs[kind][descriptor].predict(X_test)
        else:
            try:
                predicted[(descriptor,kind)] = \
                    rfcs[kind][descriptor].oob_prediction_
            except AttributeError:
                predicted[(descriptor,kind)] = \
                    rfcs[kind][descriptor].predict(X_test)

    def f_transform(x, k0, k1):
            return 100*(k0*(x/100)**(k1*0.5) - k0*(x/100)**(k1*2))

    for d,descriptor in enumerate(descriptors):
        tw = trans_weight[d]
        k0,k1 = trans_params[d]
        p_m = predicted[(descriptor,'mean')]
        p_s = predicted[(descriptor,'std')]
        predicted[(descriptor,kind)] = tw*f_transform(p_m,k0,k1) + (1-tw)*p_s
    
    predicted = predicted.stack('Descriptor')
    observed = Y_test
    score = scoring.score2(predicted,observed)
    rs = {}
    for kind in ['int','ple','dec']:
        rs[kind] = {}
        for moment in ['mean','std']:
            rs[kind][moment] = scoring.r2(kind,moment,predicted,observed)
    
    if not quiet:
        print("For subchallenge 2:")
        print("\tScore = %.2f" % score)
        for kind in ['int','ple','dec']:
            for moment in ['mean','std']: 
                print("\t%s_%s = %.3f" % (kind,moment,rs[kind][moment]))
        
    return (rfcs,score,rs)

def rfc_(X_train,Y_train,X_test_int,X_test_other,Y_test,
         max_features=1500,n_estimators=1000,max_depth=None,min_samples_leaf=1):
    print(max_features)
    def rfc_maker():
        return RandomForestRegressor(max_features=max_features,
                                     n_estimators=n_estimators,
                                     max_depth=max_depth,
                                     min_samples_leaf=min_samples_leaf,
                                     n_jobs=-1,
                                     oob_score=True,
                                     random_state=0)
        
    rfc = rfc_maker()
    rfc.fit(X_train,Y_train)
    scores = {}
    for phase,X,Y in [('train',X_train,Y_train),
                      ('test',(X_test_int,X_test_other),Y_test)]:
        if phase == 'train':
            predicted = rfc.oob_prediction_
        else:
            predicted = rfc.predict(X[1])
            predicted_int = rfc.predict(X[0])
            predicted[:,0] = predicted_int[:,0]
            predicted[:,21] = predicted_int[:,21]
        observed = Y
        score = scoring.score2(predicted,observed)
        r_int = scoring.r2('int','mean',predicted,observed)
        r_ple = scoring.r2('ple','mean',predicted,observed)
        r_dec = scoring.r2('dec','mean',predicted,observed)
        r_int_sig = scoring.r2('int','std',predicted,observed)
        r_ple_sig = scoring.r2('ple','std',predicted,observed)
        r_dec_sig = scoring.r2('dec','std',predicted,observed)
        print(("For subchallenge 2, %s phase, "
               "score = %.2f (%.2f,%.2f,%.2f,%.2f,%.2f,%.2f)"
               % (phase,score,r_int,r_ple,r_dec,r_int_sig,r_ple_sig,r_dec_sig)))
        scores[phase] = (score,r_int,r_ple,r_dec,r_int_sig,r_ple_sig,r_dec_sig)

    return rfc,scores['train'],scores['test']

# Show that random forest regression also works really well out of sample.  
def rfc_cv(X,Y_imp,Y_mask,Y_test=None,n_splits=10,n_estimators=100,
           max_features=1500,min_samples_leaf=1,max_depth=None,rfc=True):
    if Y_mask is None:
        use_Y_mask = False
        Y_mask = Y_imp
    else:
        use_Y_mask = True
    if Y_test is None:
        Y_test = Y_mask
    if rfc:
        rfc_imp = RandomForestRegressor(max_features=max_features,
                                n_estimators=n_estimators,
                                max_depth=max_depth,
                                min_samples_leaf=min_samples_leaf,
                                oob_score=False,n_jobs=-1,random_state=0)
        rfc_mask = RandomForestRegressor(max_features=max_features,
                                n_estimators=n_estimators,
                                max_depth=max_depth,
                                min_samples_leaf=min_samples_leaf,
                                oob_score=False,n_jobs=-1,random_state=0)
    else:
        rfc_imp = ExtraTreesRegressor(max_features=max_features,
                                n_estimators=n_estimators,
                                max_depth=max_depth,
                                min_samples_leaf=min_samples_leaf,
                                  oob_score=False,n_jobs=-1,random_state=0)
        rfc_mask = ExtraTreesRegressor(max_features=max_features,
                                n_estimators=n_estimators,
                                max_depth=max_depth,
                                min_samples_leaf=min_samples_leaf,
                                  oob_score=False,n_jobs=-1,random_state=0)
    test_size = 0.2
    shuffle_split = ShuffleSplit(n_splits,test_size=test_size,random_state=0)
    n_molecules = len(Y_imp)
    test_size *= n_molecules
    rs = {'int':{'mean':[],'std':[],'trans':[]},
          'ple':{'mean':[],'std':[]},
          'dec':{'mean':[],'std':[]}}
    scores = []
    for train_index,test_index in shuffle_split.split(range(n_molecules)):
        rfc_imp.fit(X[train_index],Y_imp[train_index])
        predicted_imp = rfc_imp.predict(X[test_index])
        if use_Y_mask:
            rfc_mask.fit(X[train_index],Y_mask[train_index])
            predicted_mask = rfc_mask.predict(X[test_index])
        else:
            predicted_mask = predicted_imp
        observed = Y_test[test_index]
        rs_ = {'int':{},'ple':{},'dec':{}}
        for kind1 in ['int','ple','dec']:
            for kind2 in ['mean','std']:
                if kind2 in rs[kind1]:
                    if '%s_%s' % (kind1,kind2) in ['int_mean','ple_mean',
                                                   'dec_mean']:
                        r_ = scoring.r2(kind1,kind2,predicted_imp,observed)
                    else:
                        r_ = scoring.r2(kind1,kind2,predicted_mask,observed)
                    rs_[kind1][kind2] = r_
                    rs[kind1][kind2].append(r_)
        score = scoring.rs2score2(rs_)
        scores.append(score)
        rs['int']['trans'].append(scoring.r2(None,None,
                                             f_int(predicted_imp[:,0]),
                                             observed[:,21]))
    for kind1 in ['int','ple','dec']:
        for kind2 in ['mean','std','trans']:
            if kind2 in rs[kind1]:
                mean = np.mean(rs[kind1][kind2])
                sem = np.std(rs[kind1][kind2])/np.sqrt(n_splits)
                rs[kind1][kind2] = {'mean':mean,
                                    'sem':sem}
    scores = {'mean':np.mean(scores),'sem':np.std(scores)/np.sqrt(n_splits)}
    #print("For subchallenge 2, using cross-validation with:")
    #print("\tat most %s features:" % max_features)
    #print("\tat least %s samples per leaf:" % min_samples_leaf)
    #print("\tat most %s depth:" % max_depth)
    #print("\tscore = %.2f+/- %.2f" % (scores['mean'],scores['sem']))
    for kind2 in ['mean','std','trans']:
        for kind1 in ['int','ple','dec']:
            if kind2 in rs[kind1]:
                pass#print("\t%s_%s = %.3f+/- %.3f" % (kind1,kind2,rs[kind1][kind2]['mean'],rs[kind1][kind2]['sem']))
        
    return scores,rs

def f_int(x, k0=0.718, k1=1.08):
    return 100*(k0*(x/100)**(k1*0.5) - k0*(x/100)**(k1*2))

def scan(X_train,Y_train,X_test_int,X_test_other,Y_test,max_features=None,
         n_estimators=100):
    rfcs_max_features = {}
    ns = np.logspace(1,3.48,15)
    scores_train = []
    scores_test = []
    for n in ns:
        rfc_max_features,score_train,score_test = \
            rfc_(X_train,Y_train['mean_std'],X_test_int,X_test_other,
                 Y_test['mean_std'],max_features=int(n),n_estimators=100)
        scores_train.append(score_train)
        scores_test.append(score_test)
        rfcs_max_features[n] = rfc_max_features
    rs = ['int_m','ple_m','dec_m','int_s','ple_s','dec_s']
    for i,ri in enumerate(rs):
        print(ri)
        print('maxf ',ns.round(2))
        print('train',np.array(scores_train)[:,i].round(3))
        print('test ',np.array(scores_test)[:,i].round(3))
   
    return rfc_max_features,scores_train,scores_test
    #for n,train,test in zip(ns,scores_train,scores_test):
    #    print("max_features = %d, train = %.2f, test = %.2f" % (int(n),train,test))
    #return rfcs_max_features


def mask_vs_impute(X):
    print(2)
    Y_median,imputer = dream.make_Y_obs(['training','leaderboard'],
                                        target_dilution=None,imputer='median')
    Y_mask,imputer = dream.make_Y_obs(['training','leaderboard'],
                                      target_dilution=None,imputer='mask')
    r2s_median = rfc_cv(X,Y_median['mean_std'],Y_test=Y_mask['mean_std'],
                        n_splits=20,max_features=1500,n_estimators=200,
                        min_samples_leaf=1,rfc=True)
    r2s_mask = rfc_cv(X,Y_mask['mean_std'],n_splits=20,max_features=1500,
                      n_estimators=200,min_samples_leaf=1,rfc=True)
    return (r2s_median,r2s_mask)


def compute_linear_feature_ranks(X,Y,n_resampling=10):
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    
    X = X.drop(['mean_dilution'],1)
    
    # Matrix to store the score rankings.  
    lin_ranked = np.zeros((21,X.shape[1])).astype(int) 
    
    rl = RandomizedLasso(alpha=0.025,selection_threshold=0.025,
                         n_resampling=n_resampling,random_state=25,n_jobs=1)
    for col in range(21):
        print("Computing feature ranks for descriptor #%d" % col)
        observed = Y[:,col]
        rl.fit(X,observed)
        lin_ranked[col,:] = np.argsort(rl.all_scores_.ravel())[::-1]
    return lin_ranked


def compute_linear_feature_ranks_cv(X,Y,n_resampling=10,n_splits=25):
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    
    # Matrix to store the score rankings.  
    lin_ranked = np.zeros((n_splits,21,X.shape[1])).astype(int) 
    n_molecules = int(X.shape[0]/2) # Expects an array with two dilutions
                                    # for each molecule
    shuffle_split = ShuffleSplit(n_splits,test_size=0.17,
                                 random_state=0) # This will produce the splits 
                                                 # in train/test_big that I 
                                                 # put on GitHub
    rl = RandomizedLasso(alpha=0.025,selection_threshold=0.025,
                         n_resampling=n_resampling,random_state=25,n_jobs=1)
    for col in range(21):
        # Produce the correct train and test indices.  
        cv = utils.DoubleSS(shuffle_split, n_molecules, col, X[:,-1]) 
        for j,(train,test) in enumerate(cv):
            print("Computing feature ranks for descriptor #%d, split #%d" \
                  % (col,j))
            observed = Y[train,col]
            rl.fit(X[train,:],observed)
            lin_ranked[j,col,:] = np.argsort(rl.all_scores_.ravel())[::-1]
    return lin_ranked


def master_cv(X,Y,n_estimators=50,n_splits=25,model='rf',
              alpha=10.0,random_state=0,feature_list=slice(None)):
    rs = np.zeros((21,n_splits))
    n_molecules = int(X.shape[0]/2)
     # This random state *must* be zero. 
    shuffle_split = ShuffleSplit(n_splits,test_size=0.17,random_state=0) 
    
    for col in range(21):
        print(col)
        observed = Y[:,col]
        cv = utils.DoubleSS(shuffle_split, n_molecules, col, X[:,-1])
        for j,(train,test) in enumerate(cv):
            #print(col,j)
            if model == 'rf':
                if col==0:
                    est = ExtraTreesRegressor(n_estimators=n_estimators,
                                              max_features=max_features[col], 
                                              max_depth=max_depth[col], 
                                        min_samples_leaf=min_samples_leaf[col],
                                              n_jobs=8,random_state=0)     
                else:
                    est = RandomForestRegressor(n_estimators=n_estimators,
                                                max_features=max_features[col], 
                                                max_depth=max_depth[col], 
                                        min_samples_leaf=min_samples_leaf[col],
                                                oob_score=False,n_jobs=8,
                                                random_state=0)
            elif model == 'ridge':
                est = Ridge(alpha=alpha,random_state=random_state)
            features = feature_list[j,col,:]
            est.fit(X[train,:][:,features],observed[train])
            predicted = est.predict(X[test,:][:,features])
            rs[col,j] = np.corrcoef(predicted,observed[test])[1,0]

        mean = rs[col,:].mean()
        sem = rs[col,:].std()/np.sqrt(n_splits)
        print(('Desc. %d: %.3f' % (col,mean)))
    return rs


def feature_sweep(X,Y,n_estimators=50,n_splits=25,
                  n_features=[1,2,3,4,5,10,33,100,333,1000,3333,10000],
                  model='rf',wrong_split=False,max_features='auto',
                  max_depth=None,min_samples_leaf=1,alpha=1.0,
                  lin_ranked=None,random_state=0):
    if model == 'ridge' and lin_ranked is None:
        raise Exception('Must provided "lin_ranked" to use the linear model')
    rs = np.ma.zeros((21,len(n_features),n_splits)) # Empty matrix to store correlations.  
    n_molecules = int(X_all.shape[0]/2) # Number of molecules.  
    shuffle_split = ShuffleSplit(n_molecules,n_splits,test_size=0.17,
                                 random_state=0) 
                    # This will produce the splits in train/test_big that I 
                    # put on GitHub
    
    for col in range(0,21): # For each descriptor.  
        observed = Y[:,col] # Perceptual data for this descriptor.  
        n_features_ = list(np.array(n_features)+(col==0))
        # Produce the correct train and test indices.  
        cv = DoubleSS(shuffle_split, n_molecules, col, X_all[:,-1]) 
        for j,(train,test) in enumerate(cv):
            print('Fitting descriptor #%d, split #%d' % (col,j))
            if model == 'rf': # If the model is random forest regression.  
                if col==0:
                    est = ExtraTreesRegressor(n_estimators=n_estimators,
                                              max_features=max_features,
                                              max_depth=max_depth,
                                              min_samples_leaf=min_samples_leaf,
                                              n_jobs=8,
                                              random_state=random_state)
                else:
                    est = RandomForestRegressor(n_estimators=n_estimators,
                                                max_features=max_features,
                                                max_depth=max_depth,
                                            min_samples_leaf=min_samples_leaf,
                                                oob_score=False,n_jobs=8,
                                                random_state=random_state)
            elif model == 'ridge': # If the model is ridge regression. 
                est = Ridge(alpha=alpha,fit_intercept=True,normalize=False, 
                            copy_X=True,max_iter=None,tol=0.001,solver='auto',
                            random_state=random_state)
            if rfe:  
                rfe = RFE(estimator=est, step=n_features_, 
                          n_features_to_select=1)
                rfe.fit(X[train,:],observed[train])    
            else:  
                # Fit the model on the training data.  
                est.fit(X[train,:],observed[train]) 
                if model == 'rf':
                    # Use feature importances to get ranks.
                    import_ranks = np.argsort(est.feature_importances_)[::-1]   
                elif model == 'ridge':
                    # Use the pre-computed ranks.
                    import_ranks = lin_ranked[int(j+wrong_split)%n_splits,col,:] 
            for i,n_feat in enumerate(n_features_):
                if col==0:
                    # Add one for intensity since negLogD is worthless when
                    # all concentrations are 1/1000. 
                    n_feat += 1  
                if hasattr(est,'max_features') \
                and est.max_features not in [None,'auto']:
                    if n_feat < est.max_features:
                        est.max_features = n_feat
                if rfe:
                    est.fit(X[train,:][:,rfe.ranking_<=(1+i)],observed[train])
                    predicted = est.predict(X[test,:][:,rfe.ranking_<=(1+i)])
                else:
                    #est.max_features = None
                    # Fit the model on the training data
                    # with 'max_features' features.
                    est.fit(X[train,:][:,import_ranks[:n_feat]],observed[train])
                    # Predict the test data.  
                    predicted = est.predict(X[test,:][:,import_ranks[:n_feat]]) 
                # Compute the correlation coefficient.
                rs[col,i,j] = np.corrcoef(predicted,observed[test])[1,0]  
    return rs