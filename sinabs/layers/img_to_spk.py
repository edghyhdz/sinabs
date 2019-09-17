#  Copyright (c) 2019-2019     aiCTX AG (Sadique Sheik).
#
#  This file is part of sinabs
#
#  sinabs is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  sinabs is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with sinabs.  If not, see <https://www.gnu.org/licenses/>.

import pandas as pd
from .layer import TorchLayer
from typing import Tuple
import torch


class Img2SpikeLayer(TorchLayer):
    """
    Layer to convert Images to Spikes
    """

    def __init__(
        self,
        image_shape,
        tw: int = 100,
        max_rate: float = 1000,
        layer_name: str = "img2spk",
        norm: float = 255.0,
        squeeze: bool = False,
        negative_spikes: bool = False
    ):
        """
        Layer converts images to spikes

        :param image_shape: tuple image shape
        :param tw: int Time window length
        :param max_rate: maximum firing rate of neurons
        :param layer_name: string layer name
        :param norm: the supposed maximum value of the input (default 255.0)
        :param squeeze: whether to remove singleton dimensions from the input
        :param negative_spikes: whether to allow negative spikes in response \
        to negative input
        """
        TorchLayer.__init__(
            self, input_shape=(None, *image_shape), layer_name=layer_name
        )
        self.tw = tw
        self.max_rate = max_rate
        self.norm = norm
        self.squeeze = squeeze
        self.negative_spikes = negative_spikes

    def forward(self, img_input):
        if self.squeeze:
            img_input = img_input.squeeze()
        random_tensor = torch.rand(self.tw, *tuple(img_input.shape)).to(img_input.device)
        if not self.negative_spikes:
            firing_probs = (img_input / self.norm) * (self.max_rate / 1000)
            spk_img = (random_tensor < firing_probs).float()
        else:
            firing_probs = (img_input.abs() / self.norm) * (self.max_rate / 1000)
            spk_img = (random_tensor < firing_probs).float() * img_input.sign().float()
        return spk_img

    def get_output_shape(self, input_shape: Tuple):
        # The time dimension is not included in the shape
        # NOTE: This is not true if the squeeze is false but input_shape has a batch_size
        # TODO: Fix this
        return input_shape  # (self.tw, *input_shape)

    def summary(self):
        """
        Returns a summary of this layer as a pandas Series
        """
        summary = pd.Series(
            {
                "Type": self.__class__.__name__,
                "Layer": self.layer_name,
                "Input_Shape": tuple(self.input_shape),
                "Output_Shape": tuple(self.output_shape),
                "Neurons": 0,
            }
        )
        return summary