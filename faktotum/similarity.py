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
        for instance in tqdm.tqdm(self._load_corpus("train")):
            a = Sentence(instance["sentence"], use_tokenizer=False)
            b = Sentence(instance["context"], use_tokenizer=False)
            a.entity_indices = instance["sentence_indices"]
            a.identifier = instance["sentence_identifier"]
            a.person = instance["person"]
            b.entity_indices = instance["context_indices"]
            b.identifier = instance["context_identifier"]
            b.person = instance["person"]
            point = DataPair(a, b)
            point.similar = instance["similar"]
            self.train.append(point)

        print("Test")
        for instance in tqdm.tqdm(self._load_corpus("test")):
            a = Sentence(instance["sentence"], use_tokenizer=False)
            b = Sentence(instance["context"], use_tokenizer=False)
            a.entity_indices = instance["sentence_indices"]
            a.identifier = instance["sentence_identifier"]
            a.person = instance["person"]
            b.entity_indices = instance["context_indices"]
            b.identifier = instance["context_identifier"]
            b.person = instance["person"]
            point = DataPair(a, b)
            point.similar = instance["similar"]
            self.test.append(point)

        print("Dev")
        for instance in tqdm.tqdm(self._load_corpus("dev")):
            a = Sentence(instance["sentence"], use_tokenizer=False)
            b = Sentence(instance["context"], use_tokenizer=False)
            a.entity_indices = instance["sentence_indices"]
            a.identifier = instance["sentence_identifier"]
            a.person = instance["person"]
            b.entity_indices = instance["context_indices"]
            b.identifier = instance["context_identifier"]
            b.person = instance["person"]
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

    @staticmethod
    def _get_y(data_points):
        return torch.tensor([sentence.similar for sentence in data_points]).to(flair.device)

    def forward_loss(
        self, data_points: Union[List[DataPoint], DataPoint]
    ) -> torch.tensor:
        source = self._embed_source([point.first for point in data_points])
        target = self._embed_target([point.second for point in data_points])
        y = self._get_y(data_points)
        return self.similarity_loss(source, target, y)

    def evaluate(
        self,
        data_loader: DataLoader,
        out_path: Path = None,
        embedding_storage_mode="none",
    ) -> (Result, float):
        with torch.no_grad():
            i = 0
            score = 0.0
            for data_points in data_loader:
                source = self._embed_source([point.first for point in data_points])
                target = self._embed_target([point.second for point in data_points])
                y = self._get_y(data_points)
                score += self.similarity_loss(source, target, y).item()
                i += 1
            score = score / i
        return (
            Result(
                1 - score,
                f"{score}",
                f"{score}",
                f"{score}",
            ),
            0,
        )


def test():
    corpus = FaktotumDataset("droc")
    """
    embedding = DocumentRNNEmbeddings(
        [
            BertEmbeddings(
        "/mnt/data/users/simmler/model-zoo/ner-droc"
        ),
        ],
        bidirectional=True,
        dropout=0.25,
        hidden_size=256,
        rnn_type="LSTM"
    )

    similarity_measure = torch.nn.CosineSimilarity(dim=-1)

    similarity_loss = torch.nn.CosineEmbeddingLoss()

    similarity_model = EntitySimilarity(
        source_embeddings=embedding,
        target_embeddings=embedding,
        similarity_measure=similarity_measure,
        similarity_loss=similarity_loss,
    )

    trainer: ModelTrainer = ModelTrainer(
        similarity_model, corpus, optimizer=torch.optim.SGD
    )"""

    trainer = ModelTrainer.load_checkpoint("droc-similarity-model/best-model.pt", corpus)
    trainer.train(
        "droc-similarity-model1",
        mini_batch_size=64,
        max_epochs=10,
        embeddings_storage_mode="none",
    )


if __name__ == "__main__":
    test()
    # https://omoindrot.github.io/triplet-loss#triplet-mining
    # https://gombru.github.io/2019/04/03/ranking_loss/
