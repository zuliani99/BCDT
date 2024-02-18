

import torch
import torch.nn as nn

from utils import get_text_dataloaders, read_embbedings
from FaissClustering import Faiss_KMEANS
from TrainEvaluate import Train_Evaluate

import numpy as np
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE



class Approaches(object):
	def __init__(self, timestamp, choosen_model_embedding, embeddings_dim = None, bool_ablations = False):
		self.timestamp = timestamp
		self.embeddings_dim = embeddings_dim
		self.bool_ablations = bool_ablations
		self.choosen_model_embedding = choosen_model_embedding
		self.faiss_kmeans = Faiss_KMEANS()
  
  
	def run_clustering(self, ds_name, method_name, data):
    
		x_train, x_test, y_train, y_test = data
    
		ablations_dict = {}
   
		if self.bool_ablations:
			print(f'--------------- {ds_name} - PCA & TSNE ablations ---------------')
				
			pca = PCA(n_components=2)
			tsne = TSNE()
	
			ablations_dict['pca'] = {'x_train': pca.fit_transform(x_train), 'x_test': pca.fit_transform(x_train)}
			ablations_dict['tsne'] = {'x_train': tsne.fit_transform(x_train), 'x_test': tsne.fit_transform(x_train)}
				
			for ab_name, x_reduced in ablations_dict.items():
       
				print(f'Running {ab_name} ablations\n')
    
				print(' => Saving reduced embeddings:')
				np.save(
        			f'app/embeddings/{self.choosen_model_embedding}/{ds_name}/ablations/{ab_name}_{method_name}_train.npy',
            		x_reduced['x_train']
				)
				np.save(
        			f'app/embeddings/{self.choosen_model_embedding}/{ds_name}/ablations/{ab_name}_{method_name}_test.npy',
            		x_reduced['x_test']
				)
				print(' DONE\n')
					
				self.faiss_kmeans.run_faiss_kmeans(
        			ds_name,
           			f'{method_name}_{ab_name}',
              		self.timestamp,
                	'our_ablations',
					(x_reduced['x_train'], x_reduced['x_test'], y_train, y_test)
     			)
    
			print('----------------------------------------------------------------\n')
			
		else:
			print(f'--------------- {ds_name} ---------------')
	 
			# run clusering
			self.faiss_kmeans.run_faiss_kmeans(
				ds_name,
				method_name,
				self.timestamp,
    			'our_approaches',
				(x_train, x_test, y_train, y_test)
			)

			print('------------------------------------------\n')



class MainApproch(Approaches):
	def __init__(self, common_parmas, bool_ablations):
     
		super().__init__(common_parmas['timestamp'], common_parmas['choosen_model_embedding'], bool_ablations = bool_ablations)
		self.datasets_name = common_parmas['datasets_name']


	def run(self):
	
		print(f'---------------------------------- START {self.__class__.__name__} ----------------------------------')	    
		  
		for ds_name in self.datasets_name:

			x_train, x_test, y_train, y_test = read_embbedings(ds_name, self.choosen_model_embedding)
			# [#sentence, #layers, 768] -> [#sentence, 768] 

			x_train = np.squeeze(x_train[:,-1,:])
			x_test = np.squeeze(x_test[:,-1,:])
   
			self.run_clustering(ds_name, self.__class__.__name__, (x_train, x_test, y_train, y_test))
			

		print(f'\n---------------------------------- END {self.__class__.__name__ } ----------------------------------\n\n')
  
  
  


class LayerWise(Approaches):
	def __init__(self, common_parmas, embeddings_dim, bool_ablations):
     
		super().__init__(common_parmas['timestamp'], common_parmas['choosen_model_embedding'], embeddings_dim = embeddings_dim, bool_ablations = bool_ablations)
  
		self.datasets_name = common_parmas['datasets_name']
		self.name = f'{self.__class__.__name__}_{embeddings_dim}'

  
	def run(self):
	 
		print(f'---------------------------------- START {self.name} ----------------------------------')
	 
		for ds_name in self.datasets_name:
			
			x_train, x_test, y_train, y_test = read_embbedings(ds_name, self.choosen_model_embedding)
   
			if self.embeddings_dim == 768:
				# [#sentence, #layers, 768] -> [#sentence, 768] 
       
				# mean of oll CLS tokens
				x_train, x_test = np.squeeze(np.mean(x_train, axis=1)), np.squeeze(np.mean(x_test, axis=1))
			else:
				# [#sentence, #layers, 768] -> [#sentence, #layers x 768] 
				
				# getting the CLS token concatenations from the (last 6) layers 
				#x_train = x_train[:,6:,:]
				x_train = np.reshape(x_train, (x_train.shape[0], x_train.shape[1] * x_train.shape[2]))
    
				#x_test = x_test[:,6:,:]
				x_test = np.reshape(x_test, (x_test.shape[0], x_test.shape[1] * x_test.shape[2]))

			self.run_clustering(ds_name, self.__class__.__name__, (x_train, x_test, y_train, y_test))

		
		print(f'\n---------------------------------- END {self.name} ----------------------------------\n\n')
   




class SelfAttentionLayer(nn.Module):
	def __init__(self, input_size, output_size, attention_heads):
		super(SelfAttentionLayer, self).__init__()

		self.multihead_att = nn.MultiheadAttention(input_size, attention_heads, need_weights = False)

		# Linear transformation for the output of attention heads
		self.classifier = nn.Sequential(
			nn.Dropout(p=0.5),
			nn.Linear(input_size, input_size // 2),
   			nn.ReLU(inplace=True),
			nn.Dropout(p=0.5),
			nn.Linear(input_size // 2, input_size // 4),
   			nn.ReLU(inplace=True),
			nn.Dropout(p=0.5),
			nn.Linear(input_size // 4, output_size)
		)
  
	def forward(self, x):
		print(x.shape)
		# Linear transformations for Query, Key, and Value
		attn_output = torch.flatten(self.multihead_att(x, x, x))
		outputs = self.classifier(attn_output)
		return outputs, attn_output




class LayerAggregation(Approaches):
	
	def __init__(self, params, common_parmas, embeddings_dim, bool_ablations):
		
		super().__init__(common_parmas['timestamp'], common_parmas['choosen_model_embedding'], embeddings_dim = embeddings_dim, bool_ablations = bool_ablations)
		self.datasets_name = common_parmas['datasets_name']
  
		self.tran_evaluate = Train_Evaluate(self.__class__.__name__, params, SelfAttentionLayer(self.embeddings_dim, output_size=2, attention_heads=8))
  
  
	def get_LayerAggregation_Embeddigns(self, dataloader):
  
		LA_embeds = torch.empty((0, self.embeddings_dim), dtype=torch.float32, device=self.device)		
		LA_labels = torch.empty((0), device=self.device)		
  
		self.tran_evaluate.model.eval()

		with torch.inference_mode(): # Allow inference mode
			for bert_embeds, labels in dataloader:

				bert_embeds = bert_embeds.to(self.device)
				labels = labels.to(self.device)
			
				_, embeds = self.tran_evaluate.model(bert_embeds)

				LA_embeds = torch.cat((LA_embeds, embeds), dim=0)
				LA_labels = torch.cat((LA_embeds, labels))

		return LA_embeds.cpu().numpy(), LA_labels.cpu().numpy()


					 
	def run(self):

		print(f'---------------------------------- START {self.__class__.__name__} ----------------------------------')	
  
		for ds_name in self.datasets_name:

			x_train, x_val, x_test, y_train, y_val, y_test = read_embbedings(ds_name, self.choosen_model_embedding, bool_validation=True)
   			
			# concatenation of all the CLS tokens
			#x_train = torch.reshape(x_train, (x_train.shape[0], x_train.shape[1] * x_train.shape[2]))
			#x_test = torch.reshape(x_test, (x_test.shape[0], x_test.shape[1] * x_test.shape[2]))
      
			# create tensor dataloaders
			train_dl, val_dl, test_dl = get_text_dataloaders(x_train, y_train, x_val, y_val, x_test, y_test)

			self.tran_evaluate.fit(ds_name, train_dl, val_dl)
   
			# we can for eaxample save these metrics to compare with the additional embedding
			_, _ = self.tran_evaluate.test(test_dl)
   
			x_train, y_train = self.get_LayerAggregation_Embeddigns(train_dl)
			x_val, y_val = self.get_LayerAggregation_Embeddigns(train_dl)
			x_test, y_test = self.get_LayerAggregation_Embeddigns(train_dl)
   
			x_train = np.vstack((x_train, x_val))
			y_train = np.append(y_train, y_val)
   
			self.run_clustering(ds_name, self.__class__.__name__, (x_train, x_test, y_train, y_test))
   
		print(f'\n---------------------------------- END {self.__class__.__name__} ----------------------------------\n\n')

   
