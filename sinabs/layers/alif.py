from typing import Optional, Union
import torch
from .spiking_layer import SpikingLayer
from .pack_dims import squeeze_class
from .recurrent_module import recurrent_class
from .lif import LIF
from .functional import ThresholdSubtract, ThresholdReset


__all__ = ["ALIF", "ALIFSqueeze"]

# Learning window for surrogate gradient
window = 1.0


class ALIF(SpikingLayer):
    def __init__(
        self,
        tau_mem: Union[float, torch.Tensor],
        tau_adapt: Union[float, torch.Tensor],
        adapt_scale: Union[float, torch.Tensor] = 1.8,
        threshold: Union[float, torch.Tensor] = 1.0,
        membrane_reset: bool = False,
        threshold_low: Optional[float] = None,
        membrane_subtract: Optional[float] = None,
        *args,
        **kwargs,
    ):
        """
        Pytorch implementation of a Long Short Term Memory SNN (LSNN) by Bellec et al., 2018:
        https://papers.neurips.cc/paper/2018/hash/c203d8a151612acf12457e4d67635a95-Abstract.html

        Neuron dynamics in discrete time: 

        .. math ::
            V(t+1) = \\alpha V(t) + (1-\\alpha) \\sum w.s(t)

            B(t+1) = b0 + \\text{adapt_scale } b(t)

            b(t+1) = \\rho b(t) + (1-\\rho) s(t)

            \\text{if } V_{mem}(t) >= B(t) \\text{, then } V_{mem} \\rightarrow V_{mem} - b0, b \\rightarrow 0

        where :math:`\\alpha = e^{-1/\\tau_{mem}}`, :math:`\\rho = e^{-1/\\tau_{adapt}}` 
        and :math:`w.s(t)` is the input current for a spike s and weight w.

        Parameters
        ----------
        tau_mem: float
            Membrane potential time constant.
        tau_adapt: float
            Spike threshold time constant.
        adaption: float
            The amount that the spike threshold is bumped up for every spike, after which it decays back to the initial threshold.
        threshold: float
            Spiking threshold of the neuron.
        threshold_low: float or None
            Lower bound for membrane potential.
        membrane_reset: bool
            If True, reset the membrane to 0 on spiking.
        membrane_subtract: float or None
            The amount to subtract from the membrane potential upon spiking.
            Default is equal to threshold. Ignored if membrane_reset is set.
        """
        super().__init__(
            threshold=threshold,
            threshold_low=threshold_low,
            membrane_subtract=membrane_subtract,
            membrane_reset=membrane_reset,
            *args,
            **kwargs,
        )
        self.tau_mem = tau_mem
        self.tau_adapt = tau_adapt
        self.adapt_scale = adapt_scale
        self.b_0 = threshold
        self.register_buffer("b", torch.zeros(1))
        self.reset_function = ThresholdReset if membrane_reset else ThresholdSubtract

    @property
    def alpha_mem(self):
        return torch.exp(-1/self.tau_mem)

    @property
    def alpha_adapt(self):
        return torch.exp(-1/self.tau_adapt)

    def check_states(self, input_current):
        """Initialise spike threshold states when the first input is received."""
        shape_without_time = (input_current.shape[0], *input_current.shape[2:])
        if self.v_mem.shape != shape_without_time:
            self.reset_states(shape=shape_without_time, randomize=False)

    def forward(self, input_current: torch.Tensor):
        """
        Forward pass with given data.

        Parameters
        ----------
        input_current : torch.Tensor
            Data to be processed. Expected shape: (batch, time, ...)

        Returns
        -------
        torch.Tensor
            Output data. Same shape as `input_spikes`.
        """
        # Ensure the neuron state are initialized
        self.check_states(input_current)

        time_steps = input_current.shape[1]
        
        output_spikes = []
        for step in range(time_steps):
            # Decay the spike threshold and add adaptation factor to it.
            self.b = self.alpha_adapt * self.b + (1 - self.alpha_adapt) * self.activations
            
            self.threshold = self.b_0 + self.adapt_scale*self.b

            # Decay the membrane potential and add the input currents which are normalised by tau
            self.v_mem = self.alpha_mem * self.v_mem + (1 - self.alpha_mem) * input_current[:, step]  - self.threshold * self.activations

            # Clip membrane potential that is too low
            if self.threshold_low:
                self.v_mem = torch.clamp(self.v_mem, min=self.threshold_low)

            # generate spikes
            self.activations = self.reset_function.apply(
                self.v_mem,
                self.threshold,
                self.threshold * window,
            )
            output_spikes.append(self.activations)

        output_spikes = torch.stack(output_spikes, 1)
        self.tw = time_steps
        self.spikes_number = output_spikes.abs().sum()
        return output_spikes

    def reset_states(self, shape=None, randomize=False):
        """Reset the state of all neurons and threshold states in this layer."""
        super().reset_states(shape, randomize)
        if shape is None:
            shape = self.b.shape
        if randomize:
            self.b = torch.rand(shape, device=self.b.device)
        else:
            self.b = torch.zeros(shape, device=self.b.device)

    @property
    def _param_dict(self) -> dict:
        param_dict = super()._param_dict
        param_dict.update(
            tau_mem=self.tau_mem,
            tau_adapt=self.tau_adapt,
            adapt_scale=self.adapt_scale,
        )

        return param_dict


ALIFRecurrent = recurrent_class(ALIF)
ALIFSqueeze = squeeze_class(ALIF)
ALIFRecurrentSqueeze = squeeze_class(ALIFRecurrent)