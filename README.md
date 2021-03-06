# Extract and disambiguate named entities

## Installation

```
$ pip install faktotum
```

## Getting started
You can use pre-trained models for both literary texts (`literary-texts`) and press releases (`press-texts`).

### Named Entity Recognition
```python
>>> import faktotum
>>> text = "Er hieß Eduard. Ihr Name war Klara, manchmal auch Klärchen."
>>> faktotum.ner(text, domain="literary-texts")
    sentence_id      word entity
0             0        Er    NaN
1             0      hieß    NaN
2             0    Eduard  B-PER
3             0         .    NaN
4             1       Ihr    NaN
5             1      Name    NaN
6             1       war    NaN
7             1     Klara  B-PER
8             1         ,    NaN
9             1  manchmal    NaN
10            1      auch    NaN
11            1  Klärchen  B-PER
12            1         .    NaN
```

### Named Entity Linking
You have to provide a knowledge base in a JSON file like:

```json
{
    "Q1": {
        "CONTEXTS": [
            [
                "Eduard",
                "ist",
                "ein",
                "schöner",
                "Name",
                "."]
        ],
        "ENTITY_INDICES": [
            [
                0
            ]
        ]
    },
    "Q2": {
        "CONTEXTS": [
            [
                "Klara",
                "ist",
                "auch",
                "ein",
                "schöner",
                "Name",
                "."
            ]
        ],
        "ENTITY_INDICES": [
            [
                0
            ]
        ]
    }
```

where an identifier maps to a list of contexts and a list of indices referring to entities in the contexts.

```python
>>> import json
>>> import faktotum
>>> with open("kb.json", "r", encoding="utf-8") as f:
...     data = json.load(f)
>>> kb = faktotum.KnowledgeBase(data, domain="literary-texts")
>>> text = "Er hieß Eduard. Ihr Name war Klara, manchmal auch Klärchen."
>>> faktotum.nel(text, kb, domain="literary-texts")
    sentence_id      word entity entity_id
0             0        Er    NaN       NaN
1             0      hieß    NaN       NaN
2             0    Eduard  B-PER        Q1
3             0         .    NaN       NaN
4             1       Ihr    NaN       NaN
5             1      Name    NaN       NaN
6             1       war    NaN       NaN
7             1     Klara  B-PER        Q2
8             1         ,    NaN       NaN
9             1  manchmal    NaN       NaN
10            1      auch    NaN       NaN
11            1  Klärchen  B-PER        Q2
12            1         .    NaN       NaN
```

Or with a knowledge base with two records related to press releases:

```json
{
    "Q1": {
        "CONTEXTS": [
            [
                "Apple",
                "produziert",
                "Software",
                "und",
                "Hardware",
                "."
            ]
        ],
        "ENTITY_INDICES": [
            [
                0
            ]
        ]
    },
    "Q2": {
        "CONTEXTS": [
            [
                "Apple",
                "ist",
                "ein",
                "Plattenlabel",
                "."
            ]
        ],
        "ENTITY_INDICES": [
            [
                0
            ]
        ]
    }
}
```

set the `domain` argument to `press-texts`:

```python
>>> import json
>>> import faktotum
>>> with open("kb.json", "r", encoding="utf-8") as f:
...     data = json.load(f)
>>> kb = faktotum.KnowledgeBase(data, domain="press-texts")
>>> text = "Apple hat kürzlich neue Computer vorgestellt. Das erste Musikalbum auf Apple ist 1968 erschienen."
>>> faktotum.nel(text, kb, "press-texts")
    sentence_id         word entity entity_id
0             0        Apple  B-ORG        Q1
1             0          hat    NaN       NaN
2             0     kürzlich    NaN       NaN
3             0         neue    NaN       NaN
4             0     Computer    NaN       NaN
5             0  vorgestellt    NaN       NaN
6             0            .    NaN       NaN
7             1          Das    NaN       NaN
8             1        erste    NaN       NaN
9             1   Musikalbum    NaN       NaN
10            1          auf    NaN       NaN
11            1        Apple  B-ORG        Q2
12            1          ist    NaN       NaN
13            1         1968    NaN       NaN
14            1   erschienen    NaN       NaN
15            1            .    NaN       NaN
```
