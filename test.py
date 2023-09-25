from transformers import AutoTokenizer, AutoConfig
import torch
from torch.utils.data import DataLoader, Subset
from tqdm import tqdm
import argparse
import os
from train import BertDataset
from eval import evaluate
from model import PLM_Graph
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('--device', type=str, default='cuda')
parser.add_argument('--batch', type=int, default=32, help='Batch size.')
parser.add_argument('--name', type=str, required=True, help='Name of checkpoint. Commonly as DATASET-NAME.')
parser.add_argument('--extra', default='_micro', choices=['_macro', '_micro'], help='An extra string in the name of checkpoint.')
args = parser.parse_args()

if __name__ == '__main__':
    
    #data_path_root='/scratch/ashish_k.iitr/HPT/RRM_modelWOS/pyscript/'
    data_path_root=os.path.join('../HTLA/data', args.data)
    data_path=data_path_root+'Checkpoints/'
    checkpoint = torch.load(os.path.join(data_path, args.name, 'checkpoint_best{}.pt'.format(args.extra)),
                            map_location='cpu')       
    batch_size = args.batch
    device = args.device
    extra = args.extra
    mod_name=args.name
    args = checkpoint['args'] if checkpoint['args'] is not None else args
    #data_path = os.path.join('data', args.data)


    if not hasattr(args, 'graph'):
        args.graph = False
    print(args)
    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    config = AutoConfig.from_pretrained(args.mod_type)

    label_dict = torch.load(os.path.join(data_path_root, 'bert_value_dict.pt'))
    label_dict = {i: tokenizer.decode(v, skip_special_tokens=True) for i, v in label_dict.items()}
    num_class = len(label_dict)

    dataset = BertDataset(device=device, pad_idx=tokenizer.pad_token_id, data_path=data_path_root)

    # for only bert
    '''model = ContrastModel.from_pretrained('bert-base-uncased', num_labels=num_class,
                                          contrast_loss=0,
                                          layer=0, data_path=data_path_root, multi_label=args.multi,
                                          lamb=args.lamb, threshold=args.thre, tau=args.tau)'''
    model = PLM_Graph(config, num_labels=num_class,
                                          graph=args.graph,mod_type=args.mod_type,graph_type=args.graph_type,
                                          bce_wt=args.bce_wt,dot=args.dot,
                                          layer=args.layer, data_path=args.data,
                                          tripmg=args.trpmg,trip_penalty=args.trp_pen,mglist=args.mg_list,
                                          mine=args.mine,mine_pen=args.mine_pen,netw=args.netw,min_proj=args.min_proj,label_refiner=args.label_refiner,
                                          )



    split = torch.load(os.path.join(data_path_root, 'split.pt'))
    test = Subset(dataset, split['test'])
    test = DataLoader(test, batch_size=batch_size, shuffle=False, collate_fn=dataset.collate_fn)
    model.load_state_dict(checkpoint['param'])

    model.to(device)

    truth = []
    pred = []
    index = []
    slot_truth = []
    slot_pred = []

    model.eval()
    pbar = tqdm(test)
    with torch.no_grad():
        for data, label, idx in pbar:
            padding_mask = data != tokenizer.pad_token_id
            output = model(data, padding_mask, labels=label )
            for l in label:
                t = []
                for i in range(l.size(0)):
                    if l[i].item() == 1:
                        t.append(i)
                truth.append(t)
            for l in output['logits']:
                pred.append(torch.sigmoid(l).tolist())

    pbar.close()
    scores = evaluate(pred, truth, label_dict)
    #pred_rcv=np.array(pred)
    #np_name=mod_name+extra+'.npy'
    #np.save(np_name,pred_rcv)

    macro_f1 = scores['macro_f1']
    micro_f1 = scores['micro_f1']
    print(f'Model {mod_name} with best {extra} checkpoint')
    print('macro', macro_f1, 'micro', micro_f1)
    
