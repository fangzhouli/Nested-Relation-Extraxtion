ENTITY_PREFIX = "e-"
PREDICATE_PREFIX = "p-"

EPOCHS = 3
BATCH_SIZE = 16
MAX_LAYERS = 2
MAX_ENTITY_TOKENS = 5
LEARNING_RATE = 0.1

CELL_STATE_CLAMP_VAL = 1e4
HIDDEN_STATE_CLAMP_VAL = 1e6

PREPPED_DATA_PATH = "../data/prepped_dataset_7.pickle"
XML_PATH = "../data/BioInfer_corpus_1.1.1.xml"

WORD_EMBEDDING_DIM = 256
BLSTM_OUT_DIM = 2 * WORD_EMBEDDING_DIM
HIDDEN_DIM_BERT = 768

EXCLUDE_SAMPLES = [
    681,  # has no entities
]

# options are bert, from-scratch
ENCODING_METHOD = "from-scratch"

VAL_DIMS = False
