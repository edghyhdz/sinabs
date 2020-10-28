import torch
from .functional import quantize, stochastic_rounding


class NeuromorphicReLU(torch.nn.Module):
    """
    NeuromorphicReLU layer. This layer is NOT used for Sinabs networks; it's
    useful while training analogue pyTorch networks for future use with Sinabs.

    :param quantize: Whether or not to quantize the output (i.e. floor it to \
        the integer below), in order to mimic spiking behavior.
    :param fanout: Useful when computing the number of SynOps of a quantized \
        NeuromorphicReLU. The activity can be accessed through \
        NeuromorphicReLU.activity, and is multiplied by the value of fanout.
    :param stochastic_rounding: Upon quantization, should the value be rounded stochastically or floored
        Only done during training. During evaluation mode, the value is simply floored

    """

    def __init__(self, quantize=True, fanout=1, stochastic_rounding=False):
        super().__init__()
        self.quantize = quantize
        self.stochastic_rounding = stochastic_rounding
        self.fanout = fanout

    def forward(self, inp):
        output = torch.nn.functional.relu(inp)
        if self.quantize:
            if self.stochastic_rounding:
                if self.training:
                    output = stochastic_rounding(output)
                else:
                    output = output.round()
            else:
                output = quantize(output)

        self.activity = output.sum() / len(output) * self.fanout
        return output
