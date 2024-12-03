import keras
from keras.saving import register_keras_serializable as serializable

from bayesflow.types import Tensor
from bayesflow.utils import expand_tile


@serializable(package="bayesflow.networks")
class Time2Vec(keras.Layer):
    """
    Implements the Time2Vec learnbale embedding from [1].
    [1] Kazemi, S. M., Goel, R., Eghbali, S., Ramanan, J., Sahota, J., Thakur, S., ... & Brubaker, M.
    (2019). Time2vec: Learning a vector representation of time. arXiv preprint arXiv:1907.05321.
    """

    def __init__(self, num_periodic_features: int = 8):
        super().__init__()

        self.num_periodic_features = num_periodic_features
        self.linear_weight = self.add_weight(
            shape=(1,),
            initializer="glorot_uniform",
            trainable=True,
            name="trend_weight",
        )

        self.linear_bias = self.add_weight(
            shape=(1,),
            initializer="glorot_uniform",
            trainable=True,
            name="trend_bias",
        )

        self.periodic_weights = self.add_weight(
            shape=(self.num_periodic_features,),
            initializer="glorot_normal",
            trainable=True,
            name="periodic_weights",
        )

        self.periodic_biases = self.add_weight(
            shape=(self.num_periodic_features,),
            initializer="glorot_normal",
            trainable=True,
            name="periodic_biases",
        )

    def call(self, x: Tensor, t: Tensor = None) -> Tensor:
        """Creates time representations and concatenates them to x.

        Parameters:
        -----------
        x   : Tensor of shape (batch_size, sequence_length, dim)
            The input sequence.
        t   : Tensor of shape (batch_size, sequence_length)
            Vector of times

        Returns:
        --------
        emb : Tensor
            Embedding of shape (batch_size, sequence_length, num_periodic_features + 1)
        """

        if t is None:
            t = keras.ops.linspace(0, keras.ops.shape(x)[1], keras.ops.shape(x)[1], dtype=x.dtype)
            t = expand_tile(t, keras.ops.shape(x)[0], axis=0)

        linear = t * self.linear_weight + self.linear_bias
        periodic = keras.ops.sin(t[..., None] * self.periodic_weights[None, :] + self.periodic_biases[None, :])
        emb = keras.ops.concatenate([linear[..., None], periodic], axis=-1)
        return keras.ops.concatenate([x, emb], axis=-1)
