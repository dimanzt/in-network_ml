from scapy.all import *
import pandas as pd
import numpy as np
import subprocess
import argparse
from datetime import datetime
from sklearn.externals import joblib


from decimal import Decimal
import time


l = ['hdr.ethernet.etherType', 'hdr.ipv4.protocol','ipS', 'ipD', 'df', 'mf', 'fin', 'syn', 'rst', 'psh', 'ack', 'urg', 'ece', 'cwr', 'src', 'dst',  
                                 'UDPSrcPort', 'UDPDstPort', 'hdr.ipv4.totalLen', 'first_pkt_time', 'flow_duration', 
                                 'min_pkt_len', 'max_pkt_len', 'pkts', 'avg_len', 'ex', 'ex2', 'k', 'len_variance', 'label', 'idx_fw', 'idx_bw']
def new_df(col):
    return pd.DataFrame(columns=col)



print ("Loading PCAP")


def get_ip_flag(flags):
    if flags == 'DF': 
        return 1
    elif flags == 'MF':
        return 2
    else:
        return 0

def tcp_ecn(flag):
    count = 0
    if ('E' in flag):
        count += 1   
    if ('C' in flag):
        count += 2
    if ('N' in flag):
        count += 4
    return count 

def tcp_ctrl(flag):
    count = 0
    if ('F' in flag):
        count += 1      
    if ('S' in flag):
        count += 2     
    if ('R' in flag):
        count += 4     
    if ('P' in flag):
        count += 8  
    if ('A' in flag):
        count += 16    
    if ('U' in flag):
        count += 32    
    return count 

def has_in_flag(flag, s):
    return True if s in str(flag) else False


def extract_features(f_in, loaded_model, df_flow, max_f, label):
    scapy_cap = PcapReader(f_in)
    count = 0
    cDrop = 0
    df = new_df(l)

    df_final = pd.DataFrame(columns=['idx', 'n_pkt', 'label'])

    final = []
    
    hat = 0
    ift = 0
    elset = 0
    haq = 1
    ifq = 1
    elseq = 1
    for packet in scapy_cap:
        start_time = time.time()
        tsp = 0
        tdp = 0
        usp = 0
        udp = 0
        if packet.haslayer(TCP):
            tsp = packet[TCP].sport
            tdp = packet[TCP].dport
        if packet.haslayer(UDP):
            usp = packet[UDP].sport
            udp = packet[UDP].dport

        if not packet.haslayer(IP):   
            continue

        hf = '{}{}{}{}{}{}'.format(packet[IP].src, tsp, usp, packet[IP].dst, tdp, udp)
        hb = '{}{}{}{}{}{}'.format(packet[IP].dst, tdp, udp, packet[IP].src, tsp, usp)

        h = hashlib.md5(hf.encode("utf-8")).hexdigest()
        #print(h)
        if h in df.index:        
            
            first = df.at[h, 'first_pkt_time']
            min = df.at[h, 'min_pkt_len']
            max = df.at[h, 'max_pkt_len']

            df.at[h, 'hdr.ipv4.totalLen'] = df.at[h, 'hdr.ipv4.totalLen'] + packet[IP].len 
            df.at[h, 'flow_duration'] = Decimal(packet.time) - Decimal(first)
            pkt = df.at[h, 'pkts'] +1
            df.at[h, 'pkts'] = pkt
            
            if min > packet[IP].len:
                df.at[h, 'min_pkt_len'] = packet[IP].len
            if max < packet[IP].len:
                df.at[h, 'max_pkt_len'] = packet[IP].len
            
            k = df.at[h, 'k']
            y = (packet[IP].len - k) # -k  
            n = pkt

            ex = df.at[h, 'ex'] + y
            df.at[h, 'ex'] = ex
            ex2 = df.at[h, 'ex2'] + (y * y)
            df.at[h, 'ex2'] = ex2

            df.at[h, 'len_variance'] = (ex2 - (ex * ex)/n) / (n - 1)

            df.at[h, 'avg_len'] = df.at[h, 'hdr.ipv4.totalLen'] / n

            df.at[h, 'df'] += 1 if has_in_flag(packet[IP].flags, 'DF') else 0
            df.at[h, 'mf'] += 1 if has_in_flag(packet[IP].flags, 'MF') else 0

            if packet.haslayer(TCP):
                #packet.show2()
                #print(packet[IP].id)
                df.at[h, 'fin'] += 1 if has_in_flag(packet[TCP].flags, 'F') else 0
                df.at[h, 'syn'] += 1 if has_in_flag(packet[TCP].flags, 'S') else 0
                df.at[h, 'rst'] += 1 if has_in_flag(packet[TCP].flags, 'R') else 0
                df.at[h, 'psh'] += 1 if has_in_flag(packet[TCP].flags, 'P') else 0
                df.at[h, 'ack'] += 1 if has_in_flag(packet[TCP].flags, 'A') else 0
                df.at[h, 'urg'] += 1 if has_in_flag(packet[TCP].flags, 'U') else 0
                df.at[h, 'ece'] += 1 if has_in_flag(packet[TCP].flags, 'E') else 0
                df.at[h, 'cwr'] += 1 if has_in_flag(packet[TCP].flags, 'C') else 0
        else:

            dct = dict.fromkeys(l, 0)

            hb = hashlib.md5(hb.encode("utf-8")).hexdigest()
            
            dct['idx_fw'] = h
            dct['idx_bw'] = hb                
            dct['hdr.ethernet.etherType'] = packet[Ether].type
            
            #row.at['pkt_per_sec'] = 0
            #row.at['bytes_per_sec'] = 0

            dct['hdr.ipv4.protocol'] = packet[IP].proto
            dct['hdr.ipv4.totalLen'] = packet[IP].len 
            dct['ipS'] = packet[IP].src 
            dct['ipD'] = packet[IP].dst 

            dct['df'] = 1 if has_in_flag(packet[IP].flags, 'DF') else 0
            dct['mf'] = 1 if has_in_flag(packet[IP].flags, 'MF') else 0

            if packet.haslayer(TCP):
                #print(packet[IP].id)
                dct['fin'] = 1 if has_in_flag(packet[TCP].flags, 'F') else 0
                dct['syn'] = 1 if has_in_flag(packet[TCP].flags, 'S') else 0
                dct['rst'] = 1 if has_in_flag(packet[TCP].flags, 'R') else 0
                dct['psh'] = 1 if has_in_flag(packet[TCP].flags, 'P') else 0
                dct['ack'] = 1 if has_in_flag(packet[TCP].flags, 'A') else 0
                dct['urg'] = 1 if has_in_flag(packet[TCP].flags, 'U') else 0
                dct['ece'] = 1 if has_in_flag(packet[TCP].flags, 'E') else 0
                dct['cwr'] = 1 if has_in_flag(packet[TCP].flags, 'C') else 0
            else:
                dct['fin'] = 0
                dct['syn'] = 0
                dct['rst'] = 0
                dct['psh'] = 0
                dct['ack'] = 0
                dct['urg'] = 0
                dct['ece'] = 0
                dct['cwr'] = 0                
            dct['src'] = tsp
            dct['dst'] = tdp
            dct['UDPSrcPort'] = usp
            dct['UDPDstPort'] = udp
            
            dct['min_pkt_len'] = packet[IP].len
            dct['max_pkt_len'] = packet[IP].len
            dct['first_pkt_time'] = packet.time
            dct['flow_duration'] = 0
            dct['pkts'] = 1
            dct['k'] = packet[IP].len
            dct['ex'] = 0
            dct['ex2'] = 0
            dct['avg_len'] = packet[IP].len
            
            dct['len_variance'] = 0
            df2 = pd.DataFrame(dct, columns=l, index=[h])
            #df = df.append(df2)
            df = pd.concat([df, df2])




        df_tmp = df[df['idx_fw'] == h]
        df_tmp = df_tmp.drop(columns=['first_pkt_time', 'ex', 'ex2', 'k', 'idx_bw','idx_fw', 'src', 'UDPSrcPort', 'avg_len', 'len_variance', 'label', 'ipS', 'ipD'])
        count += 1
        #print(df_tmp)

        hf = '{}{}{}{}{}{}{}'.format(packet[IP].src, tsp, usp, packet[IP].dst, tdp, udp, df.at[h, 'pkts'])

        h2 = hashlib.md5(hf.encode("utf-8")).hexdigest()

        classe = loaded_model.predict(df_tmp)[0]
        
        d = dict.fromkeys(['idx', 'n_pkt', 'label'], 0)

        d['idx'] = h
        d['n_pkt'] = df.at[h, 'pkts']
        d['label'] = classe

        final.append(d)
        #if h == '2c88dfe05a159082c51917102c87dd56':
        #    print(df_tmp)
        #    print('{} - {}'.format( df.at[h, 'pkts'], classe))


        if df_flow.at[h, 'pkts'] == df.at[h, 'pkts']:
            df.drop([h])
            cDrop +=1


        if count % 1000 == 0:
            print('pkt count: {} dropped {} avg time {}'.format(count, cDrop, (ift/hat)))
            ift = 0
            hat = 0
        
        if cDrop % 500 == 0 and cDrop != 0:
            print('dropped {} saving ../results/{}_passiva.csv'.format(cDrop, label))
            df_final = pd.DataFrame(final)
            df_final.sort_values(by=['idx', 'n_pkt'], inplace=True)
            df_final.to_csv("../results/{}_passiva.csv".format(label),sep=',', encoding='utf-8', index=False)
 
        if max_f == cDrop and max_f != 0:
            print('breaking {} == {}'.format(max_f, df.shape[0]))
            break
    
        ift +=(time.time() - start_time)
        hat += 1
    df_final = pd.DataFrame(final)
    df_final.sort_values(by=['idx', 'n_pkt'], inplace=True)
    df_final.to_csv("../results/{}_passiva.csv".format(label),sep=',', encoding='utf-8', index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process to extract features from pcap.')
    parser.add_argument('-i', help='input pcap file')
    args = parser.parse_args()
    print ("Loading PCAP")

    try: 
        df_flow = pd.read_csv("../results/dataset_flow.csv", index_col='idx_fw')
        label = args.i.replace('.pcap', '').replace('../pcap/', '')
        df_flow = df_flow[df_flow['label']==label]
        print(label)
        print (df_flow.shape)
        dfBenign = new_df(l)
        loaded_model = joblib.load('../results/tmp/finalized_model_DT.sav')
        extract_features(args.i, loaded_model, df_flow, 0, label)
    except KeyboardInterrupt: # exit on control-c
        pass
