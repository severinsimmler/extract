import itertools
import json
import uuid
from collections import defaultdict
from pathlib import Path
from typing import List, Union

import flair
import torch
from flair.data import DataPair, DataPoint, Sentence
from flair.datasets import FlairDataset
from flair.embeddings import BertEmbeddings, DocumentRNNEmbeddings
from flair.models.similarity_learning_model import (
    RankingLoss,
    SimilarityLearner,
    SimilarityMeasure,
    CosineSimilarity
)
from flair.trainers import ModelTrainer
from torch.autograd import Variable
from abc import abstractmethod

import flair
from flair.data import DataPoint, DataPair
from flair.embeddings import Embeddings
from flair.datasets import DataLoader
from flair.training_utils import Result
from flair.training_utils import store_embeddings

import torch
from torch import nn
import torch.nn.functional as F

import numpy as np

import itertools

from typing import Union, List
from pathlib import Path
import tqdm


class FaktotumDataset(FlairDataset):
    def __init__(self, name: str, in_memory: bool = True, **kwargs):
        super(FaktotumDataset, self).__init__()
        self.name = name
        self.train = list()
        self.dev = list()
        self.test = list()

        print("Train")
        for instance in tqdm.tqdm(self._load_corpus("test")):
            a = Sentence(instance["sentence"], use_tokenizer=False)
            b = Sentence(instance["context"], use_tokenizer=False)
            a.entity_indices = instance["sentence_indices"]
            b.entity_indices = instance["context_indices"]
            point = DataPair(a, b)
            point.similar = instance["similar"]
            self.train.append(point)

        print("Test")
        for instance in tqdm.tqdm(self._load_corpus("dev")):
            a = Sentence(instance["sentence"], use_tokenizer=False)
            b = Sentence(instance["context"], use_tokenizer=False)
            a.entity_indices = instance["sentence_indices"]
            b.entity_indices = instance["context_indices"]
            point = DataPair(a, b)
            point.similar = instance["similar"]
            self.test.append(point)

        print("Dev")
        for instance in tqdm.tqdm(self._load_corpus("dev")):
            a = Sentence(instance["sentence"], use_tokenizer=False)
            b = Sentence(instance["context"], use_tokenizer=False)
            a.entity_indices = instance["sentence_indices"]
            b.entity_indices = instance["context_indices"]
            point = DataPair(a, b)
            point.similar = instance["similar"]
            self.dev.append(point)

        self.data_points = self.train + self.test + self.dev

    def _load_corpus(self, dataset):
        module = Path(__file__).resolve().parent
        data = Path(
            module, "data", self.name, "similarity", f"{dataset}.json"
        ).read_text(encoding="utf-8")
        return json.loads(data)

    def __len__(self):
        return len(self.data_points)

    def __getitem__(self, index: int = 0) -> DataPair:
        return self.data_points[index]


class EntitySimilarity(SimilarityLearner):
    def __init__(self, **kwargs):
        super(EntitySimilarity, self).__init__(**kwargs)

    @staticmethod
    def _average_vectors(vectors):
        vector = vectors[0]
        for v in vectors[1:]:
            vector = vector + v
        return vector / len(vectors)

    def _embed_source(self, data_points, entity_indices):
        data_points = [point.first for point in data_points]

        self.source_embeddings.embed(data_points)

        entities = list()
        for sentence in data_points:
            entity = [sentence[index].embedding for index in sentence.entity_indices]
            entity = self._average_vectors(entity)
            entities.append(entity)
        entities = torch.stack(entities).to(flair.device)
        return Variable(entities, requires_grad=True)

    def _embed_target(self, data_points):
        data_points = [point.second for point in data_points]

        self.source_embeddings.embed(data_points)

        entities = list()
        for sentence in data_points:
            entity = [sentence[index].embedding for index in sentence.entity_indices]
            entity = self._average_vectors(entity)
            entities.append(entity)
        entities = torch.stack(entities).to(flair.device)
        return Variable(entities, requires_grad=True)

    @staticmethod
    def _get_y(data_points):
        return torch.tensor([sentence.similar for sentence in data_points]).to(flair.device)

    def forward_loss(
        self, data_points: Union[List[DataPoint], DataPoint]
    ) -> torch.tensor:
        source = self._embed_source(data_points)
        target = self._embed_target(data_points)
        y = self._get_y(data_points)
        return self.similarity_loss(source, target, y)

    def evaluate(
        self,
        data_loader: DataLoader,
        out_path: Path = None,
        embedding_storage_mode="none",
    ) -> (Result, float):
        # assumes that for each data pair there's at least one embedding per modality

        with torch.no_grad():
            # pre-compute embeddings for all targets in evaluation dataset
            target_index = {}
            all_target_embeddings = []
            for data_points in data_loader:
                target_inputs = []
                for data_point in data_points:
                    if str(data_point.second) not in target_index:
                        target_index[str(data_point.second)] = len(target_index)
                        target_inputs.append(data_point)
                if target_inputs:
                    all_target_embeddings.append(
                        self._embed_target(target_inputs).to(self.eval_device)
                    )
                store_embeddings(data_points, embedding_storage_mode)
            all_target_embeddings = torch.cat(all_target_embeddings, dim=0)  # [n0, d0]
            assert len(target_index) == all_target_embeddings.shape[0]

            ranks = []
            for data_points in data_loader:
                batch_embeddings = self._embed_source(data_points)

                batch_source_embeddings = batch_embeddings.to(self.eval_device)
                # compute the similarity
                batch_similarity_matrix = self.similarity_measure.forward(
                    [batch_source_embeddings, all_target_embeddings]
                )

                # sort the similarity matrix across modality 1
                batch_modality_1_argsort = torch.argsort(
                    batch_similarity_matrix, descending=True, dim=1
                )

                # get the ranks, so +1 to start counting ranks from 1
                batch_modality_1_ranks = (
                    torch.argsort(batch_modality_1_argsort, dim=1) + 1
                )

                batch_target_indices = [
                    target_index[str(data_point.second)] for data_point in data_points
                ]

                batch_gt_ranks = batch_modality_1_ranks[
                    torch.arange(batch_similarity_matrix.shape[0]),
                    torch.tensor(batch_target_indices),
                ]
                ranks.extend(batch_gt_ranks.tolist())

                store_embeddings(data_points, embedding_storage_mode)

        ranks = np.array(ranks)
        median_rank = np.median(ranks)
        recall_at = {k: np.mean(ranks <= k) for k in self.recall_at_points}

        results_header = ["Median rank"] + [
            "Recall@top" + str(r) for r in self.recall_at_points
        ]
        results_header_str = "\t".join(results_header)
        epoch_results = [str(median_rank)] + [
            str(recall_at[k]) for k in self.recall_at_points
        ]
        epoch_results_str = "\t".join(epoch_results)
        detailed_results = ", ".join(
            [f"{h}={v}" for h, v in zip(results_header, epoch_results)]
        )

        validated_measure = sum(
            [
                recall_at[r] * w
                for r, w in zip(self.recall_at_points, self.recall_at_points_weights)
            ]
        )

        return (
            Result(
                validated_measure,
                results_header_str,
                epoch_results_str,
                detailed_results,
            ),
            0,
        )



def test():
    corpus = FaktotumDataset("droc")
    embedding = BertEmbeddings(
        "/mnt/data/users/simmler/model-zoo/ner-droc"
    )

    similarity_measure = CosineSimilarity()

    similarity_loss = torch.nn.CosineEmbeddingLoss()

    similarity_model = EntitySimilarity(
        source_embeddings=embedding,
        target_embeddings=embedding,
        similarity_measure=similarity_measure,
        similarity_loss=similarity_loss,
    )

    trainer: ModelTrainer = ModelTrainer(
        similarity_model, corpus, optimizer=torch.optim.SGD
    )

    trainer.train(
        "smartdata-cosine-bcp-improved-loss",
        mini_batch_size=8,
        embeddings_storage_mode="none",
    )


if __name__ == "__main__":
    test()
