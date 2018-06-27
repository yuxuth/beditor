import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from os.path import exists,abspath,dirname
import itertools

from Bio import SeqIO, Alphabet, Data, Seq, SeqUtils
from Bio import motifs,Seq,AlignIO

import logging

# local scripts
from beditor.lib.global_vars  import hosts

def get_codon_table(aa, host):
    # get codon table
    codontable=Data.CodonTable.unambiguous_dna_by_id[hosts[host]]

    dcodontable=pd.DataFrame(pd.Series(codontable.forward_table))

    dcodontable.index.name='codon'
    dcodontable.columns=['amino acid']

    for cdn in codontable.stop_codons:
        dcodontable.loc[cdn,'amino acid']='*'        

    dcodontable=dcodontable.reset_index()
    rows=[]
    if isinstance(aa,list):
        for s in dcodontable['amino acid'].tolist():
            if s in aa:
                rows.append(True)
            else:
                rows.append(False)
    else:
        rows=dcodontable['amino acid']==aa
#     print(sum(rows))
    dcodontable=dcodontable.loc[rows,:].set_index('codon').reset_index()
    return dcodontable

def get_codon_usage(cuspp):
    # get codon usage stats
    dcodonusage=pd.read_csv(cuspp,sep='\t',header=5)
    cols=''.join(dcodonusage.columns.tolist()).split(' ')
    dcodonusage.columns=[cols[-1]]
    dcodonusage.index.names=cols[:-1]

    dcodonusage=dcodonusage.reset_index().set_index('Codon')
    dcodonusage['amino acid']=[SeqUtils.seq1(s) for s in dcodonusage['#AA']]
    return dcodonusage


def get_possible_mutagenesis(dcodontable,dcodonusage,
                             BEs,pos_muts,
                             host,
                            ): 
    def write_dmutagenesis(cdni,posi,codon,codonmut,ntwt,ntmut,aa,aamut,method):
        dmutagenesis.loc[cdni,'codon']=codon
        dmutagenesis.loc[cdni,'position of mutation in codon']=int(posi)
        dmutagenesis.loc[cdni,'codon mutation']=codonmut
        dmutagenesis.loc[cdni,'nucleotide']=ntwt
        dmutagenesis.loc[cdni,'nucleotide mutation']=ntmut
        dmutagenesis.loc[cdni,'amino acid']=aa
        dmutagenesis.loc[cdni,'amino acid mutation']=aamut
        dmutagenesis.loc[cdni,'mutation on strand']=method.split(' on ')[1]
        dmutagenesis.loc[cdni,'method']=method.split(' on ')[0]                        
        dmutagenesis.loc[cdni,'codon mutation usage Fraction']=dcodonusage.loc[codonmut,'Fraction']
        dmutagenesis.loc[cdni,'codon mutation usage Frequency']=dcodonusage.loc[codonmut,'Frequency']
        return dmutagenesis

    def get_sm(dmutagenesis,BEs,positions,codon,muti,cdni):
        for method in BEs:
            for posi in positions: 
                if BEs[method][0]==codon[posi]:
                    for ntmut in BEs[method][1]:
                        if posi==0:
                            codonmut='{}{}{}'.format(ntmut,codon[1],codon[2])
                        elif posi==1:
                            codonmut='{}{}{}'.format(codon[0],ntmut,codon[2])
                        elif posi==2:
                            codonmut='{}{}{}'.format(codon[0],codon[1],ntmut)
                        aamut=str(Seq.Seq(codonmut,Alphabet.generic_dna).translate(table=hosts[host]))
                        # if (aamut!='*') and (aamut!=aa): #  nonsence and synonymous
                        if muti==0:
                            cdni=cdni
                        else:
                            cdni=len(dmutagenesis)+1
                        muti+=1
                        ntwt=BEs[method][0]
                        if '-' in method.split(' on ')[1]:
                            ntwt=str(Seq.Seq(ntwt,Alphabet.generic_dna).reverse_complement())
                            ntmut=str(Seq.Seq(ntmut,Alphabet.generic_dna).reverse_complement())
                        dmutagenesis=write_dmutagenesis(**{'cdni':cdni,
                        'posi':posi+1,
                        'codon':codon,
                        'codonmut':codonmut,
                        'ntwt':ntwt,
                        'ntmut':ntmut,
                        'aa':aa,
                        'aamut':aamut,
                        'method':method})
        return dmutagenesis,muti
    def get_dm(dmutagenesis,BEs,positions_dm,codon,muti,cdni):
        for method in BEs:
            for posi1,posi2 in positions_dm: 
                if (BEs[method][0]==codon[posi1]) and (BEs[method][0]==codon[posi2]):
                    for ntmut1,ntmut2 in itertools.product(''.join(BEs[method][1]), repeat=2):
                        if (posi1==0) and (posi2==1):
                            codonmut='{}{}{}'.format(ntmut1,ntmut2,codon[2])
                        elif (posi1==1) and (posi2==2):
                            codonmut='{}{}{}'.format(codon[0],ntmut1,ntmut2)
                        elif (posi1==0) and (posi2==2):
                            codonmut='{}{}{}'.format(ntmut1,codon[1],ntmut2)
                        aamut=str(Seq.Seq(codonmut,Alphabet.generic_dna).translate(table=hosts[host]))
                        # if (aamut!='*') and (aamut!=aa): #  nonsence and synonymous
                        if muti==0:
                            cdni=cdni
                        else:
                            cdni=len(dmutagenesis)+1
                        muti+=1
                        ntwt='{}{}'.format(BEs[method][0],BEs[method][0])
                        ntmut='{}{}'.format(ntmut1,ntmut2)
                        if '-' in method.split(' on ')[1]:
                            ntwt=str(Seq.Seq(ntwt,Alphabet.generic_dna).reverse_complement())
                            ntmut=str(Seq.Seq(ntmut,Alphabet.generic_dna).reverse_complement())
                        dmutagenesis=write_dmutagenesis(
                        **{'cdni':cdni,
                        'posi':'{}{}'.format(posi1,posi2),
                        'codon':codon,
                        'codonmut':codonmut,
                        'ntwt':ntwt,
                        'ntmut':ntmut,
                        'aa':aa,
                        'aamut':aamut,
                        'method':method})
        return dmutagenesis,muti

    def get_tm(dmutagenesis,BEs,positions_tm,codon,muti,cdni):
        for method in BEs:
            for posi1,posi2,posi3 in positions_tm:
                if (BEs[method][0]==codon[posi1]) and (BEs[method][0]==codon[posi2]) and (BEs[method][0]==codon[posi3]):
                    for ntmut1,ntmut2,ntmut3 in itertools.product(''.join(BEs[method][1]), repeat=3):
                        codonmut='{}{}{}'.format(ntmut1,ntmut2,ntmut3)
                        aamut=str(Seq.Seq(codonmut,Alphabet.generic_dna).translate(table=hosts[host]))
                        # if (aamut!='*') and (aamut!=aa): #  nonsence and synonymous
                        if muti==0:
                            cdni=cdni
                        else:
                            cdni=len(dmutagenesis)+1
                        muti+=1
                        ntwt='{}{}{}'.format(BEs[method][0],BEs[method][0],BEs[method][0])
                        ntmut='{}{}{}'.format(ntmut1,ntmut2,ntmut3)
                        if '-' in method.split(' on ')[1]:
                            ntwt=str(Seq.Seq(ntwt,Alphabet.generic_dna).reverse_complement())
                            ntmut=str(Seq.Seq(ntmut,Alphabet.generic_dna).reverse_complement())
                        dmutagenesis=write_dmutagenesis(
                        **{'cdni':cdni,
                        'posi':'123',
                        'codon':codon,
                        'codonmut':codonmut,
                        'ntwt':ntwt,
                        'ntmut':ntmut,
                        'aa':aa,
                        'aamut':aamut,
                        'method':method})
        return dmutagenesis,muti

    def get_dm_combo(dmutagenesis,BEs,positions_dm,codon,muti,cdni,method):
        methods=[m for m in itertools.product(BEs.keys(),repeat=2) if ((m[0].split('on')[1]==m[1].split('on')[1])) and (m[0]!=m[1])]
        for method1,method2 in methods:
            for posi1,posi2 in positions_dm: 
                if (BEs[method1][0]==codon[posi1]) and (BEs[method2][0]==codon[posi2]):
                    ntmuts=[(n1,n2) for n1 in ''.join(BEs[method1][1]) for n2 in ''.join(BEs[method2][1])]
                    for ntmut1,ntmut2 in ntmuts:
                        if (posi1==0) and (posi2==1):
                            codonmut='{}{}{}'.format(ntmut1,ntmut2,codon[2])
                        elif (posi1==1) and (posi2==2):
                            codonmut='{}{}{}'.format(codon[0],ntmut1,ntmut2)
                        elif (posi1==0) and (posi2==2):
                            codonmut='{}{}{}'.format(ntmut1,codon[1],ntmut2)
                        aamut=str(Seq.Seq(codonmut,Alphabet.generic_dna).translate(table=hosts[host]))
                        # if (aamut!='*') and (aamut!=aa): #  nonsence and synonymous
                        if muti==0:
                            cdni=cdni
                        else:
                            cdni=len(dmutagenesis)+1
                        muti+=1
                        ntwt='{}{}'.format(BEs[method1][0],BEs[method2][0])
                        ntmut='{}{}'.format(ntmut1,ntmut2)
                        if '-' in method1.split(' on ')[1]:
                            ntwt=str(Seq.Seq(ntwt,Alphabet.generic_dna).reverse_complement())
                            ntmut=str(Seq.Seq(ntmut,Alphabet.generic_dna).reverse_complement())
                        dmutagenesis=write_dmutagenesis(
                        **{'cdni':cdni,
                        'posi':'{}{}'.format(posi1,posi2),
                        'codon':codon,
                        'codonmut':codonmut,
                        'ntwt':ntwt,
                        'ntmut':ntmut,
                        'aa':aa,
                        'aamut':aamut,
                        'method':method+' on '+method1.split('on')[1]})
        return dmutagenesis,muti

    def get_tm_combo(dmutagenesis,BEs,positions_tm,codon,muti,cdni,method):
        methods=[m for m in itertools.product(BEs.keys(),repeat=3) if ((m[0].split('on')[1]==m[1].split('on')[1]==m[2].split('on')[1])) and not (m[0]==m[1]==m[2])]
        for method1,method2,method3 in methods:
            for posi1,posi2,posi3 in positions_tm:
                if (BEs[method1][0]==codon[posi1]) and (BEs[method2][0]==codon[posi2]) and (BEs[method3][0]==codon[posi3]):
                    ntmuts=[(n1,n2,n3) for n1 in ''.join(BEs[method1][1]) for n2 in ''.join(BEs[method2][1]) for n3 in ''.join(BEs[method3][1])]
                    for ntmut1,ntmut2,ntmut3 in ntmuts:
                        codonmut='{}{}{}'.format(ntmut1,ntmut2,ntmut3)
                        aamut=str(Seq.Seq(codonmut,Alphabet.generic_dna).translate(table=hosts[host]))
                        # if (aamut!='*') and (aamut!=aa): #  nonsence and synonymous
                        if muti==0:
                            cdni=cdni
                        else:
                            cdni=len(dmutagenesis)+1
                        muti+=1
                        ntwt='{}{}{}'.format(BEs[method1][0],BEs[method2][0],BEs[method3][0])
                        ntmut='{}{}{}'.format(ntmut1,ntmut2,ntmut3)
                        if '-' in method1.split(' on ')[1]:
                            ntwt=str(Seq.Seq(ntwt,Alphabet.generic_dna).reverse_complement())
                            ntmut=str(Seq.Seq(ntmut,Alphabet.generic_dna).reverse_complement())
                        dmutagenesis=write_dmutagenesis(
                        **{'cdni':cdni,
                        'posi':'123',
                        'codon':codon,
                        'codonmut':codonmut,
                        'ntwt':ntwt,
                        'ntmut':ntmut,
                        'aa':aa,
                        'aamut':aamut,
                        'method':method+' on '+method1.split('on')[1]})
        return dmutagenesis,muti

    #double nucleotide mutations
    positions={0:'@1st position',1:'@2nd position',2:'@3rd position'}
    #double nucleotide mutations
    positions_dm=[(i,j)  for i in positions.keys() for j in positions.keys() if i<j]
    #double nucleotide mutations
    positions_tm=[[0,1,2]]

    dmutagenesis=dcodontable.copy()
    # test=True
    test=False
    for cdni in dmutagenesis.index:
        codon=dmutagenesis.loc[cdni,'codon']
        aa=dmutagenesis.loc[cdni,'amino acid']
        muti=0
        if test:
            print(codon)
        #single nucleuotide mutations
        dmutagenesis,muti=get_sm(dmutagenesis,BEs,positions,codon,muti,cdni)
        #double nucleotide mutations
        dmutagenesis,muti=get_dm(dmutagenesis,BEs,positions_dm,codon,muti,cdni)
        #triple nucleotide mutations
        dmutagenesis,muti=get_tm(dmutagenesis,BEs,positions_tm,codon,muti,cdni)
        #double nucleotide mutations combinations
        dmutagenesis,muti=get_dm_combo(dmutagenesis,BEs,positions_dm,codon,muti,cdni,method='Target-ACE')
        #triple nucleotide mutations combinations
        dmutagenesis,muti=get_tm_combo(dmutagenesis,BEs,positions_tm,codon,muti,cdni,method='Target-ACE')

    dmutagenesis['nucleotide mutation: count']=[len(s) for s in dmutagenesis['nucleotide mutation']]
    dmutagenesis=dmutagenesis.sort_values('codon')  
    # Adding information of Allowed activity window
    dmutagenesis=dmutagenesis.set_index('method').join(pos_muts)
    dmutagenesis=dmutagenesis.reset_index()
    return dmutagenesis

from beditor.lib.io_dfs import df2unstack
from os.path import abspath,dirname
def get_submap(cfg):
    mimetism_levels={'high': 1,
                     'medium': 5,
                     'low': 10}
    try:
        dsubmap=pd.read_csv('{}/data/dsubmap_{}.csv'.format(dirname(abspath(__file__)),cfg['host'])).set_index('AA1')
    except:
        dsubmap=pd.read_csv('data/dsubmap_{}.csv'.format(cfg['host'])).set_index('AA1')
    dsubmap.index.name='amino acid'
    dsubmap.columns.name='amino acid mutation'
    dsubmap=dsubmap.T

    dsubmaptop=pd.DataFrame(columns=dsubmap.columns,index=dsubmap.index)
    dsubmaptop=dsubmaptop.fillna(False)
    for i in dsubmap.index:
        for c in dsubmap:
            if i==c:
                dsubmaptop.loc[i,c]=True

    dsubmaptop_=dsubmaptop.copy()
    for c in dsubmap:
        dsubmaptop.loc[dsubmap.nlargest(mimetism_levels[cfg['mimetism_level']],c).index,c]=True
    import seaborn as sns
    sns.heatmap(dsubmaptop.astype(int),square=True)
    plt.savefig('{}/heatmap_submap.svg'.format(cfg['datad']))
    dsubmaptop=df2unstack(dsubmaptop,col='mimetic')
    dsubmaptop.to_csv('{}/dsubmaptop.svg'.format(cfg['datad']))
    dsubmaptop=dsubmaptop[dsubmaptop['mimetic']]
    return dsubmaptop

def filterdmutagenesis(dmutagenesis,cfg):
    logging.info('filtering: dmutagenesis.shape: ',dmutagenesis.shape)    
    # filter by mutation_type
    if not cfg['mutation_type'] is None:
        if cfg['mutation_type']=='S':
            dmutagenesis=dmutagenesis.loc[(dmutagenesis['amino acid']==dmutagenesis['amino acid mutation'])]
        elif cfg['mutation_type']=='N':
            dmutagenesis=dmutagenesis.loc[(dmutagenesis['amino acid']!=dmutagenesis['amino acid mutation'])]
        logging.info('dmutagenesis.shape: ',dmutagenesis.shape)    
    # filter by nonsense
    if not cfg['keep_mutation_nonsense'] is None:
        if not cfg['keep_mutation_nonsense']:
            dmutagenesis=dmutagenesis.loc[(dmutagenesis['amino acid mutation']!='*'),:]
        logging.info('dmutagenesis.shape: ',dmutagenesis.shape)    

    # filter by mutation per codon
    if not cfg['max_subs_per_codon'] is None:
        dmutagenesis=dmutagenesis.loc[(dmutagenesis['nucleotide mutation: count']==cfg['max_subs_per_codon']),:]
        logging.info('dmutagenesis.shape: ',dmutagenesis.shape)    

    # filter by method
    if not cfg['BEs'] is None:
        dmutagenesis=dmutagenesis.loc[dmutagenesis['method'].isin(cfg['BEs']),:]
        logging.info('dmutagenesis.shape: ',dmutagenesis.shape)    

    # filter by submap
    if not cfg['submap_type'] is None:
        if cfg['submap_type']=='M':
            dsubmap=get_submap(cfg)
        elif cfg['submap_type']=='P':
            if cfg['dsubmap_preferred_path'] is None:    
                logging.error('submap_type is P and dsubmap_preferred_path is None')
            else:
                dsubmap=pd.read_csv(cfg['dsubmap_preferred_path']) # has two cols: amino acid and amino acid mutation
        elif cfg['submap_type']=='both':
            dsubmap=get_submap(cfg).append(pd.read_csv(cfg['dsubmap_preferred_path'])).drop_duplicates()
        dmutagenesis=pd.merge(dsubmap,dmutagenesis,on=['amino acid','amino acid mutation'],how='inner')
        logging.info('dmutagenesis.shape: ',dmutagenesis.shape)    

    # filter non interchageables
    if not cfg['non_intermutables'] is None:
        non_intermutables=list(itertools.permutations(''.join(cfg['non_intermutables']),2))
        dmutagenesis.loc[(dmutagenesis.apply(lambda row: not (row['amino acid'], row['amino acid mutation']) in non_intermutables, axis=1)),:]    
        logging.info('dmutagenesis.shape: ',dmutagenesis.shape)    
    return dmutagenesis

from beditor.lib.global_vars import BEs,pos_muts
def dseq2dmutagenesis(cfg):
    cfg['datad']=cfg[cfg['step']]
    cfg['plotd']=cfg['datad']
    dmutagenesisp='{}/dmutagenesis.csv'.format(cfg['datad'])
    if not exists(dmutagenesisp) or cfg['force']:
        dseq=pd.read_csv('{}/dseq.csv'.format(cfg[cfg['step']-1]))
        aas=list(dseq['aminoacid: wild-type'].unique())#['S','T','Y']

        dcodontable=get_codon_table(aa=aas, host=cfg['host'])

        dcodonusage=get_codon_usage(cuspp='{}/../data/64_1_1_all_nuclear.cusp.txt'.format(abspath(dirname(__file__))))

        dmutagenesis=get_possible_mutagenesis(dcodontable,dcodonusage,
        #                          aa=aas,
                                              BEs=BEs,pos_muts=pos_muts,
                                     host=cfg['host'])
        dmutagenesis=filterdmutagenesis(dmutagenesis,cfg)
        dmutagenesis.to_csv(dmutagenesisp)

        print('Possible 1 nucleotide mutations:')
        print(dmutagenesis.set_index('amino acid')[['amino acid mutation','method','codon','codon mutation',
        #               'position of mutation in codon','mutation on strand',
        #               'nucleotide','nucleotide mutation',
                     ]])
        for aa in aas:
            print(aa+' can be mutated to:')
            print(list(dmutagenesis.loc[dmutagenesis.loc[:,'amino acid']==aa,:].loc[:,'amino acid mutation'].unique()))