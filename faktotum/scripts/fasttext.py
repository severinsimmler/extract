import argparse
import json
import logging
import time
from pathlib import Path

import faktotum

logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO)


def run():
    logging.info("👋 Hi, you are about to train a fastText model.")

    parser = argparse.ArgumentParser(description="Train fastText on a custom corpus.")
    parser.add_argument(
        "--model", help="Path to pre-trained model (optional).", required=False
    )
    parser.add_argument("--corpus", help="Path to the corpus directory.", required=True)
    parser.add_argument(
        "--algorithm",
        help="Algorithm to use, either 'cbow' or 'skipgram'.",
        default="cbow",
    )
    parser.add_argument("--epochs", help="Epochs to train.", required=True, type=int)

    args = parser.parse_args()

    corpus_path = Path(args.corpus).resolve()
    if args.model:
        model_path = Path(args.model).resolve()
        fasttext = faktotum.FastText.load(model_path)
        mode = "pretrained-cbow"
    else:
        sg = {"skipgram": 1, "cbow": 0}.get(args.algorithm, 0)
        fasttext = faktotum.FastText(sg=sg)
        mode = f"plain-{args.algorithm}"

    if corpus_path.is_dir():
        corpus = faktotum.load_corpus(corpus_path)
        tokens = [list(document.tokens) for document in corpus]
    else:
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        tokens = [
            [token for sentence in document for token in sentence]
            for document in corpus.values()
        ]

    fasttext.train(tokens, epochs=args.epochs)

    model_path = Path(corpus_path.parent, f"{corpus_path.stem}-{mode}.fasttext")
    logging.info(f"Saving model to {model_path}...")
    fasttext.save(model_path)