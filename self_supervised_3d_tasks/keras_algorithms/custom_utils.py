import json
import struct
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import numpy as np

from tensorflow.keras import Model, Input
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.layers import Dense
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.utils import multi_gpu_model

from self_supervised_3d_tasks.free_gpu_check import aquire_free_gpus
from self_supervised_3d_tasks.ifttt_notify_me import shim_outputs, Tee
from self_supervised_3d_tasks.keras_models.unet import downconv_model


def init(f, name="training", NGPUS=1):
    config_filename = Path(__file__).parent / "config.json"

    if (len(sys.argv)) > 1:
        config_filename = sys.argv[1]

    with open(config_filename, "r") as file:
        args = json.load(file)
        args["root_config_file"] = config_filename

    print("###########################################")
    print("{} {} with parameters: ".format(name, args))
    print("###########################################")

    aquire_free_gpus(NGPUS)
    c_stdout, c_stderr = shim_outputs()  # I redirect stdout / stderr to later inform us about errors

    with redirect_stdout(Tee(c_stdout, sys.stdout)):  # needed to actually capture stdout
        with redirect_stderr(Tee(c_stderr, sys.stderr)):  # needed to actually capture stderr
            f(**args)


def apply_prediction_model(layer_in, x, multi_gpu=False, lr=1e-3):
    dim1 = 1024
    dim2 = 1024

    x = Dense(dim1, activation="relu")(x)
    x = Dense(dim2, activation="relu")(x)
    x = Dense(1, activation="relu")(x)

    model = Model(inputs=layer_in, outputs=x)
    if multi_gpu >= 2:
        model = multi_gpu_model(model, gpus=multi_gpu)
    model.compile(
        optimizer=Adam(lr=lr), loss="mse", metrics=["mae"]
    )

    return model


def apply_encoder_model_3d(input_shape, code_size):
    model = downconv_model(input_shape)
    encoder_output = Dense(code_size)(model.outputs[0])

    enc_model = Model(model.inputs[0], encoder_output, name='encoder')
    return enc_model


def apply_encoder_model(input_shape, code_size):
    res_net = ResNet50(input_shape=input_shape, include_top=False, weights=None, pooling="max")
    encoder_output = Dense(code_size)(res_net.outputs[0])

    enc_model = Model(res_net.inputs[0], encoder_output, name='encoder')
    return enc_model


def load_permutations_3d(permutation_path=str(Path(__file__).parent.parent / "permutations" /
                                              "permutations3d_100_max.bin")):
    with open(permutation_path, "rb") as f:
        int32_size = 4
        s = f.read(int32_size * 2)
        [num_perms, c] = struct.unpack("<ll", s)
        perms = []
        for _ in range(num_perms * c):
            s = f.read(int32_size)
            x = struct.unpack("<l", s)
            perms.append(x[0])
        perms = np.reshape(perms, [num_perms, c])

    return perms, num_perms


def load_permutations(permutation_path=str(Path(__file__).parent.parent / "permutations" /
                                           "permutations_100_max.bin")):
    """Loads a set of pre-defined permutations."""
    with open(permutation_path, "rb") as f:
        int32_size = 4
        s = f.read(int32_size * 2)
        [num_perms, c] = struct.unpack("<ll", s)
        perms = []
        for _ in range(num_perms * c):
            s = f.read(int32_size)
            x = struct.unpack("<l", s)
            perms.append(x[0])
        perms = np.reshape(perms, [num_perms, c])

    # The bin file used index [1,9] for permutation, updated to [0, 8] for index.
    perms = perms - 1
    return perms, num_perms
