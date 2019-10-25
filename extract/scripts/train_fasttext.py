import argparse
from pathlib import Path
import time

import extract


log = extract.logger(__file__)


def run():
    log.info("👋 Hi, you are about to train a fastText model.")

    parser = argparse.ArgumentParser(description="Train fastText on a custom corpus.")
    parser.add_argument("--model", help="Path to pre-trained model.", required=True)
    parser.add_argument("--corpus", help="Path to the corpus directory.", required=True)
    parser.add_argument("--epochs", help="Number of epochs to train.", required=True)

    args = parser.parse_args()

    corpus_path = Path(args.corpus)
    model_path = Path(args.model)

    corpus = extract.Corpus(corpus_path)
    fasttext = extract.FastText(model_path)

    tokens = corpus.tokens()
    fasttext.train(tokens, epochs=args.epochs)

    now = int(time.time())
    model_path = Path(model_path.parent, f"{now}.fasttext")
    log.info(f"Saving model to {model_path}...")
    fasttext.model.save(model_path)
