"""
extract.corpus.api
~~~~~~~~~~~~~~~~~~

This module implements the high-level API for text processing.
"""

from pathlib import Path
from typing import Union

from extract import utils
from extract.corpus.core import Document, Corpus


def load_corpus(directory: Union[str, Path]) -> Corpus:
    """Loads a text corpus.

    Parameters
    ----------
    directory
        Path to the corpus directory.

    Returns
    -------
    A new :class:`Corpus` object.
    """
    documents = (Document(path) for path in Path(directory).glob("*.txt"))
    return Corpus(documents)


def tokenize_corpus(directory):
    """Loads and tokenizes a text corpus.

    Parameters
    ----------
    directory
        Path to the corpus directory.

    Returns
    -------
    A list of dictionaries with document name and tokens.
    """
    return [
        {document.name: list(document.tokens)} for document in load_corpus(directory)
    ]


def sentencize_corpus(directory):
    """Loads, sentencizes and tokenizes a text corpus.

    Parameters
    ----------
    directory
        Path to the corpus directory.

    Returns
    -------
    A list of dictionaries with document name and tokens split by sentences.
    """
    return [
        {document.name: [list(sentence.tokens) for sentence in document.sentences]}
        for document in load_corpus(directory)
    ]
