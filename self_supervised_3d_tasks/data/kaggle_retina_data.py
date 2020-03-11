from pathlib import Path

import albumentations as ab
import cv2
import numpy as np
import pandas as pd
from PIL import Image
from sklearn.utils import resample
from tensorflow.python.keras.preprocessing.image import random_zoom

from self_supervised_3d_tasks.data.generator_base import DataGeneratorBase


class KaggleGenerator(DataGeneratorBase):
    def __init__(
            self,
            base_path,
            dataset_table,
            batch_size=8,
            shuffle=False,
            sample_classes_uniform=False,
            suffix=".jpeg",
            multilabel=False,
            augment=False):

        if sample_classes_uniform and not shuffle:
            raise ValueError("shuffle and sample_classes_uniform have to be both active")

        self.augment = augment
        self.multilabel = multilabel
        self.suffix = suffix
        self.dataset = dataset_table

        if sample_classes_uniform:
            df_majority = self.dataset[self.dataset.level == 0]
            df_minorities = [self.dataset[self.dataset.level == i] for i in range(1, 5)]
            df_minorities = [resample(minority, replace=True, n_samples=len(df_majority))
                             for minority in df_minorities]

            self.dataset = pd.concat([df_majority] + df_minorities)
            self.dataset = self.dataset.sample(frac=1)  # dont make them appear in order

        self.base_path = Path(base_path)

        file_list = list(range(len(self.dataset)))
        super().__init__(file_list, batch_size, shuffle, pre_proc_func)

    def load_image(self, index):
        path = self.base_path / self.dataset.iloc[index][0]
        image = Image.open(path.with_suffix(self.suffix))

        arr = np.array(image, dtype="float32")
        arr = arr / 255.0
        return arr

    def data_generation(self, list_files_temp):
        data_x = []
        data_y = []

        for c in list_files_temp:
            image = self.load_image(c)
            label = self.dataset.iloc[c][1]

            # TODO: MOVE this to a separate preprocessing step
            if self.augment:
                image = random_zoom(image, zoom_range=(0.85, 1.15), channel_axis=2, row_axis=0, col_axis=1, fill_mode='constant', cval=0.0)
                image = ab.HorizontalFlip()(image=image)["image"]
                image = ab.VerticalFlip()(image=image)["image"]

            if self.multilabel:
                if label == 0:
                    label = [1, 0, 0, 0, 0]
                elif label == 1:
                    label = [1, 1, 0, 0, 0]
                elif label == 2:
                    label = [1, 1, 1, 0, 0]
                elif label == 3:
                    label = [1, 1, 1, 1, 0]
                elif label == 4:
                    label = [1, 1, 1, 1, 1]
                label = np.array(label)

            data_x.append(image)
            data_y.append(label)

        data_x = np.stack(data_x)
        data_y = np.stack(data_y)

        return data_x, data_y


def get_kaggle_generator(data_path, csv_file, train_split=None, val_split=None, train_data_generator_args={},
                         test_data_generator_args={}, val_data_generator_args={}, **kwargs):
    dataset = pd.read_csv(csv_file)

    if val_split:
        train_split = int(len(dataset) * train_split)
        val_split = int(len(dataset) * val_split)

        train = dataset.iloc[0:train_split]
        val = dataset.iloc[train_split:train_split + val_split]
        test = dataset.iloc[train_split + val_split:]

        train_data_generator = KaggleGenerator(data_path, train, **train_data_generator_args)
        val_data_generator = KaggleGenerator(data_path, val, **val_data_generator_args)
        test_data_generator = KaggleGenerator(data_path, test, **test_data_generator_args)
        return train_data_generator, val_data_generator, test_data_generator
    elif train_split:
        train_split = int(len(dataset) * train_split)

        train = dataset.iloc[0:train_split]
        val = dataset.iloc[train_split:]

        train_data_generator = KaggleGenerator(data_path, train, **train_data_generator_args)
        val_data_generator = KaggleGenerator(data_path, val, **val_data_generator_args)
        return train_data_generator, val_data_generator
    else:
        return KaggleGenerator(data_path, dataset, **train_data_generator_args)
