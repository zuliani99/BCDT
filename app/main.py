# -*- coding: utf-8 -*-

from utils import accuracy_score, get_dataloaders, get_datasets
from transformers import BertTokenizer, BertModel

from approaches.MainApproch import MainApproch
from approaches.LayerWise import LayerWise
from approaches.LayerAggregation import LayerAggregation

from competitros.BertLinears import BertLinears
from competitros.BertLSTM import BertLSTM
from competitros.BertGRU import BertGRU

import torch
import torch.nn as nn

import copy


device = torch.device('cuda:2' if torch.cuda.is_available() else 'cpu')


def main():
    
	embedding_split_perc = 0.1
    
	batch_size = 64
	epochs = 5
	patience = 3

	tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
	model = BertModel.from_pretrained("bert-base-uncased").to(device)
  
	dataloaders = get_dataloaders(get_datasets(), tokenizer, batch_size)

	loss_fn = nn.CrossEntropyLoss()
 
	params = {
		'device': device,
		'batch_size': batch_size,
  		'model': model,
    	'tokenizer': tokenizer,
     	'embedding_split_perc': embedding_split_perc,
      	'loss_fn': loss_fn,
		'score_fn': accuracy_score,
		'patience': patience,
		'epochs': epochs
	}

	# our approaches
	main_approach = MainApproch(device, dataloaders, model, tokenizer, embedding_split_perc)
	layer_wise = LayerWise(device, dataloaders, model, tokenizer, embedding_split_perc)
	layer_aggregation = LayerAggregation(copy.deepcopy(params), dataloaders)
 
	
	# competitors
	bert_linears = BertLinears(copy.deepcopy(params), dataloaders)
 
	bert_lstm = BertLSTM(copy.deepcopy(params), dataloaders, bidirectional=False)
 
	bert_lstm_bi = BertLSTM(copy.deepcopy(params), dataloaders, bidirectional=True)
 
	bert_gru = BertGRU(copy.deepcopy(params), dataloaders)
 
 
 
	methods = [
		# our approaches
		#main_approach,
		#layer_wise,
		layer_aggregation,

		# competitors
		#bert_linears,
		#bert_lstm,
		#bert_lstm_bi,
		#bert_gru
  
		# baselines
	]
 
	for method in methods:
		method.run()


if __name__ == "__main__":
    main()
    

