"""Leser betingelsesfiler (YAML). En betingelse kan arve fra en annen med «arver: fil.yaml»
og trenger da bare å inneholde det som er annerledes."""
import copy
from pathlib import Path

import yaml


def _flett(base, over):
    ut = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(ut.get(k), dict):
            ut[k] = _flett(ut[k], v)
        else:
            ut[k] = copy.deepcopy(v)
    return ut


def last_betingelse(sti):
    sti = Path(sti)
    with open(sti, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "arver" in data:
        base = last_betingelse(sti.parent / data.pop("arver"))
        base.pop("navn", None)
        data = _flett(base, data)
    data.setdefault("navn", sti.stem)
    return data
