#!/usr/bin/env python
# coding: utf-8

import os
import sys
import argparse

import pytorch_lightning as pl
import torch
from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint
from pytorch_lightning.loggers import WandbLogger
from torch.utils.data import DataLoader, random_split
import wandb

sys.path.append("../py")
sys.path.append("../lib/BioInfer_software_1.0.1_Python3/")

from bioinferdataset import BioInferDataset
from config import *

from INN import INNModelLightning, collate_func



def set_device():
    if torch.cuda.is_available():
        device = torch.device("cuda:0")
        print("Running on the GPU")
        GPUS = 1
    else:
        device = torch.device("cpu")
        print("Running on the CPU")
        GPUS = 0
    return GPUS


def load_dataset():
    dataset = BioInferDataset(XML_PATH)
    if os.path.isfile(PREPPED_DATA_PATH):
        dataset.load_samples_from_pickle(PREPPED_DATA_PATH)
    else:
        dataset.prep_data()
        dataset.samples_to_pickle(PREPPED_DATA_PATH)
    return dataset


def split_data(dataset):
    train_max_range = round(0.7 * len(dataset))
    val_max_range = round(0.9 * len(dataset))
    test_max_range = len(dataset)

    train_idx = range(0, train_max_range)
    val_idx = range(train_max_range, val_max_range)
    test_idx= range(val_max_range,test_max_range)

    train_set, val_set, test_set = random_split(dataset, lengths=[len(train_idx), len(val_idx), len(test_idx)])

    return train_set, val_set, test_set


def get_full_set_avg_distribution(datset):
    labels = torch.cat([sample["labels"] for sample in datset])
    num_elements = labels.numel()
    percent_ones = labels.sum() / num_elements

    return percent_ones

def get_sample_avg_distribution(dataset):
    counter = 0
    percent_ones = 0
    for sample in dataset:
        counter += 1
        labels = sample["labels"]
        num_elements = labels.numel()
        percent_ones += labels.sum() / num_elements

    percent_ones = percent_ones / counter

    return percent_ones

def train(run_name, encoding_method, learning_rate, batch_size, guided_training, epochs, freeze_bert_epoch, nll_positive_weight):
    """Train an INN model and log the training info to wandb.

    Args:
        run_name (str): A name assigned to this run. The name will appear on
            Wandb. The default is 'test'.

    """
    GPUS = set_device()
    dataset = load_dataset()
    train_set, val_set, test_set = split_data(dataset)
    train_distribution1 = get_full_set_avg_distribution(train_set)
    train_distribution2 = get_sample_avg_distribution(train_set)

    torch.autograd.set_detect_anomaly(True)

    train_data_loader = DataLoader(
        train_set,
        collate_fn=collate_func,
        batch_size=batch_size,
        drop_last=True,
        shuffle=False,
    )
    val_data_loader = DataLoader(
        val_set, collate_fn=collate_func, batch_size=VAL_BATCH_SIZE, shuffle=VAL_SHUFFLE
    )
    test_data_loader = DataLoader(
        test_set, collate_fn=collate_func, batch_size=TEST_BATCH_SIZE,
    )

    model = INNModelLightning(
        vocab_dict=dataset.vocab_dict,
        element_to_idx=dataset.element_to_idx,
        hidden_dim_bert=HIDDEN_DIM_BERT,
        output_bert_hidden_states=False,
        word_embedding_dim=WORD_EMBEDDING_DIM,
        encoding_method=encoding_method,
        train_distribution=torch.tensor([train_distribution1, train_distribution2]),
        learning_rate=learning_rate,
        freeze_bert_epoch=freeze_bert_epoch,
        nll_positive_weight=nll_positive_weight
    )

    wandb_config = {
        "GPUS": int(GPUS),
        "batch_size": batch_size,
        "val_batch_size":VAL_BATCH_SIZE,
        "val_shuffle":VAL_SHUFFLE,
        "max_layers": MAX_LAYERS,
        "learning_rate": learning_rate,
        "word_embedding_dim": WORD_EMBEDDING_DIM,
        "exclude_samples": EXCLUDE_SAMPLES,
        "freeze_BERT_epoch": freeze_bert_epoch,
        "encoding_method": encoding_method,
        "nll_positive_weight": nll_positive_weight
        # "guided_training": guided_training
    }

    wandb_logger = WandbLogger(
        name=run_name,
        project="nested-relation-extraction",
        entity="ner",
        config=wandb_config,
        log_model=True,
    )
    wandb_logger.watch(model, log="gradients", log_freq=1)

    checkpoint_callback = ModelCheckpoint(monitor='val_loss', dirpath=wandb.run.dir, save_top_k=1)

    trainer = pl.Trainer(
        gpus=GPUS,
        progress_bar_refresh_rate=1,
        automatic_optimization=False,
        num_sanity_val_steps=2,
        max_epochs=epochs,
        val_check_interval=0.25,
        logger=wandb_logger,
        checkpoint_callback=checkpoint_callback, # save the model after each epoch
    )

    trainer.fit(model, train_data_loader, val_data_loader)

    test_results = trainer.test(model,test_dataloaders=test_data_loader)
    print(test_results)

def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-N', '--name',
        nargs='?',
        default='test',
        type=str
    )
    parser.add_argument(
        '-E', '--encoding-method',
        nargs='?',
        default=ENCODING_METHOD,
        type=str
    )
    parser.add_argument(
        '-L', '--learning-rate',
        nargs='?',
        default=LEARNING_RATE,
        type=float
    )
    parser.add_argument(
        '-B', '--batch-size',
        nargs='?',
        default=BATCH_SIZE,
        type=int
    )
    parser.add_argument(
        '-P', '--epochs',
        nargs='?',
        default=EPOCHS,
        type=int
    )
    parser.add_argument(
        '-F', '--freeze-bert-epoch',
        nargs='?',
        default='2',
        type=int
    )
    parser.add_argument(
        '-W', '--nll-positive-weight',
        nargs='?',
        default='1',
        type=float
    )
    parser.add_argument('--guided-training', dest='guided_training', action='store_true')
    parser.set_defaults(guided_training=False)

    return parser.parse_args(args)

if __name__ == '__main__':
    args = parse_args(sys.argv[1:])
    train(args.name, args.encoding_method, args.learning_rate, args.batch_size, args.guided_training, args.epochs, args.freeze_bert_epoch, args.nll_positive_weight)
