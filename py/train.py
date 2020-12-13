#!/usr/bin/env python
# coding: utf-8

import re
import sys
import os
import numpy as np
import torch
from time import time
from torch import nn
from torch.utils.data import DataLoader, random_split
from torch.nn import functional as functional
from torch.nn.utils.rnn import pad_sequence, pack_padded_sequence
from torch.utils.tensorboard import SummaryWriter
import pytorch_lightning as pl
from pytorch_lightning.loggers import WandbLogger
from tqdm import tqdm
from pathlib import Path
import wandb

sys.path.append("../py")
sys.path.append("../lib/BioInfer_software_1.0.1_Python3/")

from config import (
    ENTITY_PREFIX,
    PREDICATE_PREFIX,
    EPOCHS,
    WORD_EMBEDDING_DIM,
    VECTOR_DIM,
    HIDDEN_DIM,
    RELATION_EMBEDDING_DIM,
    BATCH_SIZE,
    MAX_LAYERS,
    MAX_ENTITY_TOKENS,
    CELL_STATE_CLAMP_VAL,
    HIDDEN_STATE_CLAMP_VAL,
    XML_PATH,
    PREPPED_DATA_PATH,
    LEARNING_RATE,
    EXCLUDE_SAMPLES,
)

BATCH_SIZE = 2

from bioinferdataset import BioInferDataset
from INN import INNModelLightning
from daglstmcell import DAGLSTMCell


def collate_func(batch):

    cat_keys = ["element_names","A","T","S","L","labels","is_entity"]
    list_keys = ["tokens","entity_spans"]

    if type(batch) == dict:
        batch = [batch]
    new_batch = {}
    for key in cat_keys:
        new_batch[key] = torch.cat([sample[key] for sample in batch])
    for key in list_keys:
        new_batch[key] = [sample[key] for sample in batch]
    return new_batch


if __name__ == "__main__":
    if torch.cuda.is_available():
        device = torch.device("cuda:0")
        print("Running on the GPU")
        GPUS = 1
    else:
        device = torch.device("cpu")
        print("Running on the CPU")
        GPUS = 0

    dataset = BioInferDataset(XML_PATH)
    if os.path.isfile(PREPPED_DATA_PATH):
        dataset.load_samples_from_pickle(PREPPED_DATA_PATH)
    else:
        dataset.prep_data()
        dataset.samples_to_pickle(PREPPED_DATA_PATH)

    train_max_range = round(0.8 * len(dataset))
    train_idx = range(0, train_max_range)
    val_idx = range(train_max_range, len(dataset))

    torch.autograd.set_detect_anomaly(True)

    train_set, val_set = random_split(dataset, lengths=[len(train_idx), len(val_idx)])

    train_data_loader = DataLoader(
        train_set, collate_fn=collate_func, batch_size=BATCH_SIZE
    )
    val_data_loader = DataLoader(val_set, collate_fn=collate_func, batch_size=1)

    model = INNModelLightning(
        vocab_dict=dataset.vocab_dict,
        element_to_idx=dataset.element_to_idx,
        word_embedding_dim=WORD_EMBEDDING_DIM,
        relation_embedding_dim=RELATION_EMBEDDING_DIM,
        hidden_dim=HIDDEN_DIM,
        cell_state_clamp_val=CELL_STATE_CLAMP_VAL,
        hidden_state_clamp_val=HIDDEN_STATE_CLAMP_VAL,
    )

    wandb_config = {
        "batch_size": BATCH_SIZE,
        "max_layers": MAX_LAYERS,
        "learning_rate": LEARNING_RATE,
        "cell_state_clamp_val": CELL_STATE_CLAMP_VAL,
        "hidden_state_clamp_val": HIDDEN_STATE_CLAMP_VAL,
        "vector_dim": VECTOR_DIM,
        "word_embedding_dim": WORD_EMBEDDING_DIM,
        "hidden_dim": HIDDEN_STATE_CLAMP_VAL,
        "relation_embedding_dim": RELATION_EMBEDDING_DIM,
        "exclude_samples": EXCLUDE_SAMPLES,
    }

    # wandb_logger = WandbLogger(
    #     name="test",
    #     project="nested-relation-extraction",
    #     entity="ner",
    #     config=wandb_config,
    #     log_model=True,
    # )
    # wandb_logger.watch(model, log="gradients", log_freq=1)

    trainer = pl.Trainer(
        gpus=GPUS,
        progress_bar_refresh_rate=20,
        automatic_optimization=False,
        num_sanity_val_steps=2,
        max_epochs=3,
        val_check_interval=0.25,
        # logger=wandb_logger,
    )

    trainer.fit(model, train_data_loader, val_data_loader)
