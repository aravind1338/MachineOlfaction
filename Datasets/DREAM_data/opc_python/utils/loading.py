import os, sys, csv, ast, time, json

import numpy as np
import pandas as pd

from __init__ import *
import opc_python
from opc_python import * # Import constants.  
ROOT_PATH = os.path.split(opc_python.__path__[0])[0]
from opc_python.utils import scoring,search

DATA_PATH = os.path.join(ROOT_PATH,'data')
PREDICTION_PATH = os.path.join(ROOT_PATH,'predictions')

def load_perceptual_data(kind, just_headers=False, raw=False):
    if type(kind) is list:
        dfs = [load_perceptual_data(k, raw=raw) for k in kind]
        df = pd.concat(dfs)
        return df
    if kind in ['training','training-norep','replicated']:
        kind2 = 'TrainSet'
    elif kind == 'leaderboard':
        kind2 = 'LeaderboardSet'
    elif kind == 'testset':
        kind2 = 'TestSet'
    else:
        raise ValueError("No such kind: %s" % kind)
    
    if kind in ['training-norep','replicated']:
        training = load_perceptual_data('training')
        with_replicates = [x[1:3] for x in training.index if x[3]==1]
    data = []
    file_path = os.path.join(DATA_PATH,'%s.txt' % kind2)
    with open(file_path) as f:
        reader = csv.reader(f, delimiter="\t")
        for line_num,line in enumerate(reader):
            if line_num > 0:
                line[0:6] = [x.strip() for x in line[0:6]]
                line[2] = 1 if line[2]=='replicate' else 0
                line[6:] = [float('NaN') if x=='NaN' else float(x) \
                            for x in line[6:]]
                line[0] = CID = int(line[0])
                dilution = line[4]
                mag = dilution2magnitude(dilution)
                CID_dilution = (CID,mag)
                if kind == 'training-norep':
                    if CID_dilution not in with_replicates:
                        data.append(line)
                elif kind == 'replicated':
                    if CID_dilution in with_replicates:
                        data.append(line)
                else:
                    data.append(line)
            else:
                headers = line
                if just_headers:
                    return headers
    df = pd.DataFrame(data,columns=headers)
    if not raw:
        df = format_perceptual_data(df)
    return df


def format_perceptual_data(perceptual_data, target_dilution=None,
                           use_replicates=True, subjects=range(1,50)):
    p = perceptual_data
    p.rename(columns={'Compound Identifier':'CID',
                      'Odor':'Name',
                      'subject #':'Subject'},inplace=True)
    p['Dilution'] = [dilution2magnitude(x) for x in p['Dilution']]
    p.set_index(['CID','Dilution','Replicate','Subject','Name'],inplace=True)
    p = p.unstack(['Subject'])
    descriptors = get_descriptors()
    dfs = [p[descriptor] for descriptor in descriptors]
    pd.options.mode.chained_assignment = None
    for i,desc in enumerate(descriptors):
        dfs[i]['Descriptor'] = \
            desc.split('/')[1 if desc.startswith('VAL') else 0].title()
        dfs[i].set_index('Descriptor',append=True,inplace=True)
    df = pd.concat(dfs)
    df.rename(columns={x:int(x) for x in df.columns},inplace=True)
    df = df[sorted(df.columns)]
    df.reset_index(level='Name',inplace=True)
    df.insert(1,'Solvent',None)
    df = df.transpose()
    df.index.name = ''
    df = df.transpose()
    df.columns = [['Metadata']*2+['Subject']*49,df.columns]
    df = df.reorder_levels(['Descriptor','CID','Dilution','Replicate'])
    df = df.sortlevel()
    descriptors = get_descriptors(format=True)
    # Sort descriptors in paper order
    df = df.T[descriptors].T
    df['Subject'] = df['Subject'].astype(float)
    return df


def get_descriptors(format=False):
    headers = load_perceptual_data('training', just_headers=True)
    desc = headers[6:]
    if format:
        desc = [desc[col].split('/')[1 if col==1 else 0] for col in range(21)]
        desc = [desc[col][0]+desc[col][1:].lower() for col in range(21)]
    return desc


def preformat_perceptual_data(kind):
    """Get leaderboard and testset data into the same file format
    as training data"""
    
    if kind == 'leaderboard':
        target_name = 'LeaderboardSet'
        data_name = 'LBs1'
    elif kind == 'testset':
        target_name = 'TestSet'
        data_name = 'GS'
    else:
        raise Exception("Expected 'leaderboard' or 'testset'.")
    new_file_path = os.path.join(DATA_PATH,'%s.txt' % target_name)
    f_new = open(new_file_path,'w')
    writer = csv.writer(f_new,delimiter="\t")
    training_file_path = os.path.join(DATA_PATH,'TrainSet.txt')
    headers = list(pd.read_table(training_file_path).columns)
    descriptors = headers[6:]
    writer.writerow(headers)
    dilutions_file_path = os.path.join(DATA_PATH,'dilution_%s.txt' % kind)
    dilutions = pd.read_table(dilutions_file_path,index_col=0,header=0,
                                  names=['CID','Dilution'])
    lines_new = {}
    data_path = os.path.join(DATA_PATH,'%s.txt' % data_name)
    with open(data_path) as f:
        reader = csv.reader(f, delimiter="\t")
        for line_num,line in enumerate(reader):
            if line_num > 0:
                CID,subject,descriptor,value = line
                CID = int(CID)
                subject = int(subject)
                dilution = dilutions.loc[CID]['Dilution']
                mag = dilution2magnitude(dilution)
                if descriptor == 'INTENSITY/STRENGTH':
                    high = mag < 1e-3
                else:
                    high = mag > 1e-3
                line_id = '%d_%d_%d' % (CID,subject,mag)
                if line_id not in lines_new:
                    lines_new[line_id] = [CID,'N/A',0,
                                          'high' if high else 'low',
                                          dilution,subject]+['NaN']*21
                lines_new[line_id][6+descriptors.index(descriptor.strip())] = \
                    value
    
    for line_id in sorted(lines_new,
                          key=lambda x:[int(_) for _ in x.split('_')]):
        line = lines_new[line_id]
        writer.writerow(line)
    f_new.close()


def make_nspdk_dict(CIDs):
    nspdk_CIDs = pd.read_csv('%s/derived/nspdk_cid.csv' % DATA_PATH, 
                                 header=None, dtype='int').as_matrix().squeeze()
    # Start to load the NSPDK features.  
    with open('%s/derived/nspdk_r3_d4_unaug.svm' % DATA_PATH) as f:
        nspdk_dict = {}
        i = 0
        while True:
            x = f.readline()
            if not len(x):
                break
            CID = nspdk_CIDs[i]
            i += 1
            if CID in CIDs:
                key_vals = x.split(' ')[1:]
                for key_val in key_vals:
                    key,val = key_val.split(':')
                    if key in nspdk_dict:
                        nspdk_dict[key][CID] = val
                    else:
                        nspdk_dict[key] = {CID:val}
    # Only include NSPDK features known for more than one of our CIDs
    nspdk_dict = {key:value for key,value in nspdk_dict.items() if len(value)>1} 
    return nspdk_dict


def get_molecular_data(sources,CIDs):
    if 'dragon' not in sources:
        sources = ['dragon']+sources
    dfs = {}
    for source in sources:
        if source == 'dragon':
            mdd_file_path = os.path.join(DATA_PATH,
                                         'molecular_descriptors_data.txt')
            df = pd.read_csv(mdd_file_path,delimiter='\t',index_col=0)
        if source == 'episuite':
            df = pd.read_table('%s/DREAM_episuite_descriptors.txt' % DATA_PATH,
                               index_col=0).drop('SMILES',1)
            df = df.loc[CIDs]
            df.iloc[:,47] = 1*(df.iloc[:,47]=='YES ')
        if source == 'morgan':
            df = pd.read_csv('%s/morgan_sim.csv' % DATA_PATH, index_col=0)
            df.index.rename('CID',inplace=True)
            df = df.loc[CIDs]
        if source == 'nspdk':
            nspdk_dict = make_nspdk_dict(CIDs)
            df = pd.DataFrame(index=CIDs,columns=nspdk_dict.keys())
            for feature,facts in nspdk_dict.items():
                for CID,value in facts.items():
                    df.loc[CID,feature] = value
        if source == 'gramian':
            nspdk_CIDs = pd.read_csv('%s/derived/nspdk_cid.csv' % DATA_PATH, 
                                     header=None, dtype='int')\
                                     .as_matrix().squeeze()
            # These require a large file that is not on GitHub, but can be obtained separately.  
            df = pd.read_table('%s/derived/nspdk_r3_d4_unaug_gramian.mtx' \
                               % DATA, delimiter=' ', header=None)
            CID_indices = [list(nspdk_CIDs).index(CID) for CID in CIDs]
            df = df[CID_indices,:]
        print("%s has %d features for %d molecules." % \
              (source.title(),df.shape[1],df.shape[0]))
        dfs[source] = df
    df = pd.concat(dfs,axis=1)

    print("There are now %d total features." % (df.shape[1]))
    return df


def get_CID_dilutions(kind, target_dilution=None):
    if type(kind) is list:
        x = []
        for k in kind:
            x += get_CID_dilutions(k, target_dilution=target_dilution)
        return sorted(list(set(x)))
    assert kind in ['training','training-norep','replicated',
                    'leaderboard','testset']
    """Return CIDs for molecules that will be used for:
        'leaderboard': the leaderboard to determine the provisional 
                       leaders of the competition.
        'testset': final testing to determine the winners 
                   of the competition."""
    if kind in ['training','replicated','leaderboard','testset']:
        data = []
        perceptual_data = load_perceptual_data(kind)
        for i,row in perceptual_data.iterrows():
            replicate = row.name[3]
            if replicate or kind != 'replicated':
                CID = row.name[1]
                dilution = row.name[2]
                dilutions = perceptual_data.loc['Intensity'].loc[CID]\
                                           .index.get_level_values('Dilution')
                high = dilution == dilutions.max()
                if target_dilution == 'high' and not high:
                    continue
                if target_dilution == 'low' and high:
                    continue
                elif target_dilution not in [None,'high','low'] and \
                     dilution != target_dilution:
                     continue
                data.append((CID,dilution))#,high))
        data = list(set(data))
    elif kind == 'training-norep':
        training = set(get_CID_dilutions('training',
                                         target_dilution=target_dilution))
        replicated = set(get_CID_dilutions('replicated',
                                           target_dilution=target_dilution))
        data = list(training.difference(replicated))
    return sorted(data)

def get_CIDs(kind, target_dilution=None):
    CID_dilutions = get_CID_dilutions(kind, target_dilution=target_dilution)
    CIDs = [x[0] for x in CID_dilutions]
    return sorted(list(set(CIDs)))

def get_CID_rank(kind,dilution=-3):
    """Returns CID dictionary with 1 if -3 dilution is highest, 
    0 if it is lowest, -1 if it is not present.
    """

    CID_dilutions = get_CID_dilutions(kind)
    CIDs = set([int(_.split('_')[0]) for _ in CID_dilutions])
    result = {}
    for CID in CIDs:
        high = '%d_%g_%d' % (CID,dilution,1)
        low = '%d_%g_%d' % (CID,dilution,0)
        if high in CID_dilutions:
            result[CID] = 1
        elif low in CID_dilutions:
            result[CID] = 0
        else:
            result[CID] = -1
    return result

def dilution2magnitude(dilution):
    denom = dilution.replace('"','').replace("'","")\
                    .split('/')[1].replace(',','')
    return np.log10(1.0/float(denom))


def load_data_matrix(kind='training',gold_standard_only=False,
                     only_replicates=False):
    """
    Loads the data into a 6-dimensional matrix:
    Indices are:
     subject number (0-48)
     CID index
     descriptor number (0-20)
     dilution rank (1/10=0, 1/1000=1, 1/100000=2, 1/1000000=3)
     replicate (original=0, replicate=1)
    Data is masked so locations with no data are not included 
    in statistics on this array.  
    """

    _, perceptual_obs_data = load_perceptual_data(kind)
    CIDs = get_CIDs(kind)
    data = np.ma.zeros((49,len(CIDs),21,4,2),dtype='float')
    data.mask +=1
    for line in perceptual_obs_data:
        CID_index = CIDs.index(int(line[0]))
        subject = int(line[5])
        is_replicate = line[2]
        #is_replicate = False
        dilution_index = ['1/10','1/1,000','1/100,000','1/10,000,000']\
                         .index(line[4])
        for i,value in enumerate(line[6:]):
            indices = subject-1,CID_index,i,dilution_index,int(is_replicate)
            if value != 'NaN':
                if gold_standard_only:
                    if (i==0 and dilution_index==1) \
                    or (i>0 and line[3]=='high'):
                        data[indices] = float(value)
                else:
                    data[indices] = float()
    if only_replicates:
        only_replicates = data.copy()
        only_replicates.mask[:,:,:,:,0] = (data.mask[:,:,:,:,0] \
                                        + data.mask[:,:,:,:,1])>0
        only_replicates.mask[:,:,:,:,1] = (data.mask[:,:,:,:,0] \
                                        + data.mask[:,:,:,:,1])>0
        data = only_replicates
    return data


"""Output"""

# Write predictions for each subchallenge to a file.  
def open_prediction_file(subchallenge,kind,name):
    prediction_file_path = os.path.join(PREDICTION_PATH,\
                                        'challenge_%d_%s_%s.txt' \
                                        % (subchallenge,kind,name))
    f = open(prediction_file_path,'w')
    writer = csv.writer(f,delimiter='\t')
    return f,writer

def write_prediction_files(Y,kind,subchallenge,name):
    f,writer = open_prediction_file(subchallenge,kind,name=name)
    CIDs = get_CIDs(kind)
    perceptual_headers, _ = load_perceptual_data('training')

    # Subchallenge 1.
    if subchallenge == 1:
        writer.writerow(["#oID","individual","descriptor","value"])
        for subject in range(1,NUM_SUBJECTS+1):
            for j in range(NUM_DESCRIPTORS):
                for i,CID in enumerate(CIDs):
                    descriptor = perceptual_headers[-NUM_DESCRIPTORS:][j]
                    value = Y['subject'][subject][i,j].round(3)
                    writer.writerow([CID,subject,descriptor,value])
        f.close()
    
    # Subchallenge 2.
    elif subchallenge == 2:
        writer.writerow(["#oID","descriptor","value","std"])
        for j in range(NUM_DESCRIPTORS):
            for i,CID in enumerate(CIDs):
                descriptor = perceptual_headers[-NUM_DESCRIPTORS:][j]
                value = Y['mean_std'][i,j].round(3)
                std = Y['mean_std'][i,j+NUM_DESCRIPTORS].round(3)
                writer.writerow([CID,descriptor,value,std])
        f.close()

def make_prediction_files(rfcs,X_int,X_other,target,subchallenge,Y_test=None,
                          intensity_mask=None,write=True,
                          trans_weight=np.zeros(21),
                          trans_params=np.ones((21,2)),regularize=[0.8],
                          name=None):
    if len(regularize)==1 and type(regularize)==list:
        regularize = regularize*21
    if name is None:
        name = '%d' % time.time()

    n_obs = X_other.shape[0]
    descriptors = get_descriptors(format=True)
    n_subjects = 49
    kinds = ['int','ple','dec']
    moments = ['mean','std']    
    
    if subchallenge == 1:
        Y = pd.Panel(items=range(1,n_subjects+1),major_axis=X_other.index,
                     minor_axis=pd.Series(descriptors,name='Descriptor'))
        for col,descriptor in enumerate(descriptors):
            X = X_int if descriptor=='Intensity' else X_other
            if descriptor!='Intensity' or intensity_mask is None:
                mol = X_other.index
            else:
                mol = intensity_mask
            for subject in range(1,n_subjects+1):
                Y[subject][descriptor].loc[mol] = \
                    rfcs[subject][descriptor].predict(X)
        
        # Regularize
        Y_mean = Y.mean(axis=0)
        for subject in range(1,n_subjects+1):
            Y[subject] = regularize[col]*Y_mean \
                       + (1-regularize[col])*Y[subject]

        if Y_test:
            predicted = Y.to_frame()
            observed = Y_test['Subject']
            #observed = dream.filter_Y_dilutions(Y_test,'gold')['Subject']
            print(scoring.score_summary(predicted,observed))
            
    if subchallenge == 2:
        def f_transform(x, k0, k1):
            return 100*(k0*(x/100)**(k1*0.5) - k0*(x/100)**(k1*2))
        
        Y = pd.Panel(items=moments,major_axis=X_other.index,
                     minor_axis=pd.Series(descriptors,name='Descriptor'))

        for col,descriptor in enumerate(descriptors):
            X = X_int if descriptor == 'Intensity' else X_other
            if descriptor!='Intensity' or intensity_mask is None:
                mol = X_other.index
            else:
                mol = intensity_mask
            for moment in moments:
                Y[moment][descriptor].loc[mol] = \
                    rfcs[moment][descriptor].predict(X)
        
        
        for col,descriptor in enumerate(descriptors):
            tw = trans_weight[col]
            k0,k1 = trans_params[col]
            y_m = Y['mean'][descriptor]
            y_s = Y['std'][descriptor]
            Y['std'][descriptor] = tw*f_transform(y_m,k0,k1) + (1-tw)*y_s
        
        if Y_test is not None:
            print(scoring.score_summary2(Y,Y_test,mask=True))
            
    if write:
        write_prediction_files(Y,target,subchallenge,name)
        print('Wrote to file with suffix "%s"' % name)
    return Y
    

def load_eva_data(save_formatted=False):
    eva_file_path = os.path.join(DATA_PATH,'eva_100_training_data.json')
    with open(eva_file_path) as f:
        eva_json = json.load(f)

    smile_cids = {}
    for smile in eva_json.keys():
        smile_cids[smile] = search.smile2cid(smile)

    cid_smiles = {cid:smile for smile,cid in smile_cids.items()}
    eva_cids = list(smile_cids.values())
    available_cids = []
    eva_data = []
    for kind in ('training','leaderboard','testset'):
        dream_cids = get_CIDs(kind)
        print(("Out of %d CIDs from the %s data, "
               "we have EVA data for %d of them."
               % (len(dream_cids),kind,
                  len(set(dream_cids).intersection(eva_cids)))))
    for cid in dream_cids:
        if cid in cid_smiles:
            available_cids.append(cid)

    available_cids = sorted(available_cids)
    for cid in available_cids:
        smile = cid_smiles[cid]
        eva_data.append(eva_json[smile])

    if save_formatted:
        np.savetxt(os.path.join(DATA_PATH,'derived','eva_cids.dat'),
                   available_cids)
        np.savetxt(os.path.join(DATA_PATH,'derived','eva_descriptors.dat'),
                   eva_data)

    return (available_cids,eva_data)