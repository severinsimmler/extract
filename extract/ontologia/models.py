"""
extract.ontologia.api
~~~~~~~~~~~~~~~~~~~~~

This module implements models to help defining an ontology.
"""

import abc
from pathlib import Path
import logging
import json
from typing import Iterable, List, Optional, Union

import gensim
import sklearn.metrics
import sklearn.feature_extraction
import scipy

from extract import utils
from extract.corpus.core import Corpus


class TfIdf:
    token2index = dict()
    vectorizer = sklearn.feature_extraction.text.TfidfVectorizer(
        lowercase=False, tokenizer=utils.tokenize
    )

    @classmethod
    def load(cls, matrix: Path, vocabulary: Path):
        tfidf = cls()
        tfidf.matrix = scipy.sparse.load_npz(matrix)
        tfidf.index2token = json.loads(vocabulary.read_text(encoding="utf-8"))
        return tfidf

    def save(self, directory: Path):
        matrix_filepath = Path(directory, "coo-matrix.npz")
        vocabulary_filepath = Path(directory, "vocabulary.json")
        scipy.sparse.save_npz(matrix_filepath, self.matrix)
        vocabulary_filepath.write_text(json.dumps(self.index2token), encoding="utf-8")

    def fit_weights(self, corpus: Corpus):
        texts = (document.content for document in corpus)
        self.vectorizer.fit_transform(texts)
        self.weights = dict(
            zip(self.vectorizer.get_feature_names(), self.vectorizer.idf_)
        )

    def build_matrix(self, corpus: Corpus, window: int = 5):
        row = list()
        column = list()
        values = list()
        for document in corpus:
            tokens = list(document.tokens)
            for position, token in enumerate(tokens):
                i = self.token2index.setdefault(token, len(self.token2index))
                start = max(0, position - window)
                end = min(len(tokens), position + window + 1)
                for position2 in range(start, end):
                    if position2 == position:
                        continue
                    j = self.token2index.setdefault(
                        tokens[position2], len(self.token2index)
                    )
                    values.append(self.weights.get(tokens[position2], 1))
                    row.append(i)
                    column.append(j)
        self.index2token = {
            str(index): token for token, index in self.token2index.items()
        }
        self.matrix = scipy.sparse.coo_matrix((values, (row, column))).tocsr()

    def most_similar(self, token: str, n: int) -> List[str]:
        similarities = sklearn.metrics.pairwise.cosine_similarity(
            self.matrix, dense_output=False
        )
        token_index = self.token2index[token]
        column = similarities[token_index].todense()
        column = (-column).argsort()
        return [self.index2token[str(index)] for index in column[:, 1 : n + 1].A1]


class Embedding(abc.ABC):
    @abc.abstractclassmethod
    def load(self):
        pass

    def save(self, filepath: Path):
        self.model.save(str(filepath))

    def train(self, corpus: Corpus, epochs: int = 10):
        logging.info("Tokenizing corpus...")
        tokens = [list(document.tokens) for document in corpus]
        if self.pretrained:
            logging.info("Updating vocabulary...")
            self.model.build_vocab(tokens, update=True)
        else:
            logging.info("Building vocabulary...")
            self.model.build_vocab(tokens)
        logging.info("Start training...")
        self.model.train(
            sentences=corpus, total_examples=self.model.corpus_count, epochs=epochs
        )
        logging.info("Training was successful!")

    def most_similar(self, token: str, n: int = 10) -> List[str]:
        return [token[0] for token in self.model.wv.most_similar(token, topn=n)]


class Word2Vec(Embedding):
    def __init__(self, size: int = 300, sg: int = 0, window: int = 5, seed: int = 23):
        self.pretrained = False
        self.model = gensim.models.word2vec.Word2Vec(
            size=size, sg=sg, window=window, seed=seed
        )

    @classmethod
    def load(cls, filepath: Path):
        word2vec = cls()
        word2vec.pretrained = True
        logging.info("Loading pre-trained word2vec model...")
        # source: https://devmount.github.io/GermanWordEmbeddings/
        word2vec.model = gensim.models.word2vec.Word2Vec.load(str(filepath))


class FastText(Embedding):
    def __init__(
        self,
        size: int = 300,
        window: int = 5,
        sg: int = 0,
        negative: int = 10,
        min_n: int = 5,
        max_n: int = 5,
        seed: int = 23,
    ):
        self.pretrained = False
        self.model = gensim.models.fasttext.FastText(
            size=size,
            window=window,
            sg=sg,
            negative=negative,
            min_n=min_n,
            max_n=max_n,
            seed=seed,
        )

    @classmethod
    def load(cls, filepath: Path):
        fasttext = cls()
        fasttext.pretrained = True
        if filepath.suffix == ".bin":
            logging.info("Loading pre-trained Facebook fastText model...")
            # source: https://fasttext.cc/docs/en/crawl-vectors.html
            fasttext.model = gensim.models.fasttext.load_facebook_model(str(filepath))
        else:
            logging.info("Loading pre-trained custom fastText model...")
            fasttext.model = gensim.models.fasttext.FastText.load(str(filepath))
