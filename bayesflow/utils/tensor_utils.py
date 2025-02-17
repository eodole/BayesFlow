from collections.abc import Sequence
from typing import TypeVar

import keras
import numpy as np

from bayesflow.types import Tensor
from . import logging

T = TypeVar("T")


def expand(x: Tensor, n: int, side: str):
    if n < 0:
        raise ValueError(f"Cannot expand {n} times.")

    match side:
        case "left":
            idx = [None] * n + [...]
        case "right":
            idx = [...] + [None] * n
        case str() as name:
            raise ValueError(f"Invalid side {name!r}. Must be 'left' or 'right'.")
        case other:
            raise TypeError(f"Invalid side type {type(other)!r}. Must be str.")

    return x[tuple(idx)]


def expand_as(x: Tensor, y: Tensor, side: str):
    return expand_to(x, keras.ops.ndim(y), side)


def expand_to(x: Tensor, dim: int, side: str):
    return expand(x, dim - keras.ops.ndim(x), side)


def expand_left(x: Tensor, n: int) -> Tensor:
    """Expand x to the left n times"""
    if n < 0:
        raise ValueError(f"Cannot expand {n} times.")

    idx = [None] * n + [...]
    return x[tuple(idx)]


def expand_left_as(x: Tensor, y: Tensor) -> Tensor:
    """Expand x to the left, matching the dimension of y"""
    return expand_left_to(x, keras.ops.ndim(y))


def expand_left_to(x: Tensor, dim: int) -> Tensor:
    """Expand x to the left, matching dim"""
    return expand_left(x, dim - keras.ops.ndim(x))


def expand_right(x: Tensor, n: int) -> Tensor:
    """Expand x to the right n times"""
    if n < 0:
        raise ValueError(f"Cannot expand {n} times.")

    idx = [...] + [None] * n
    return x[tuple(idx)]


def expand_right_as(x: Tensor, y: Tensor) -> Tensor:
    """Expand x to the right, matching the dimension of y"""
    return expand_right_to(x, keras.ops.ndim(y))


def expand_right_to(x: Tensor, dim: int) -> Tensor:
    """Expand x to the right, matching dim"""
    return expand_right(x, dim - keras.ops.ndim(x))


def expand_tile(x: Tensor, n: int, axis: int) -> Tensor:
    """Expand and tile x along the given axis n times"""
    if keras.ops.is_tensor(x):
        x = keras.ops.expand_dims(x, axis)
    else:
        x = np.expand_dims(x, axis)

    return tile_axis(x, n, axis=axis)


def pad(x: Tensor, value: float | Tensor, n: int, axis: int, side: str = "both") -> Tensor:
    """
    Pad x with n values along axis on the given side.
    The pad value must broadcast against the shape of x, except for the pad axis, where it must broadcast against n.
    """
    if not keras.ops.is_tensor(value):
        value = keras.ops.full((), value, dtype=keras.ops.dtype(x))

    shape = list(keras.ops.shape(x))
    shape[axis] = n

    p = keras.ops.broadcast_to(value, shape)
    match side:
        case "left":
            return keras.ops.concatenate([p, x], axis=axis)
        case "right":
            return keras.ops.concatenate([x, p], axis=axis)
        case "both":
            return keras.ops.concatenate([p, x, p], axis=axis)
        case str() as name:
            raise ValueError(f"Invalid side {name!r}. Must be 'left', 'right', or 'both'.")
        case _:
            raise TypeError(f"Invalid side type {type(side)!r}. Must be str.")


def size_of(x) -> int:
    """
    :param x: A nested structure of tensors.
    :return: The total memory footprint of x, ignoring view semantics, in bytes.
    """
    if keras.ops.is_tensor(x) or isinstance(x, np.ndarray):
        return int(keras.ops.size(x)) * np.dtype(keras.ops.dtype(x)).itemsize

    # flatten nested structure
    x = keras.tree.flatten(x)

    # get unique tensors by id
    x = {id(tensor): tensor for tensor in x}

    # sum up individual sizes
    return sum(size_of(tensor) for tensor in x.values())


def tile_axis(x: Tensor, n: int, axis: int) -> Tensor:
    """Tile x along the given axis n times"""
    repeats = [1] * keras.ops.ndim(x)
    repeats[axis] = n

    if keras.ops.is_tensor(x):
        return keras.ops.tile(x, repeats)

    return np.tile(x, repeats)


# we want to annotate this as Sequence[PyTree[Tensor]], but static type checkers do not support PyTree's type expansion
def tree_concatenate(structures: Sequence[T], axis: int = 0, numpy: bool = None) -> T:
    """Concatenate all tensors in the given sequence of nested structures.
    All objects in the given sequence must have the same structure.
    The output will adhere to this structure.

    :param structures: A sequence of nested structures of tensors.
        All structures in the sequence must have the same layout.
        Tensors in the same layout location must have compatible shapes for concatenation.
    :param axis: The axis along which to concatenate tensors.
    :param numpy: Whether to use numpy or keras for concatenation.
        Will convert all items in the structures to numpy arrays if True, tensors otherwise.
        Defaults to True if all tensors are numpy arrays, False otherwise.
    :return: A structure of concatenated tensors with the same layout as each input structure.
    """
    if numpy is None:
        numpy = not any(keras.tree.flatten(keras.tree.map_structure(keras.ops.is_tensor, structures)))

    if numpy:
        structures = keras.tree.map_structure(keras.ops.convert_to_numpy, structures)

        def concat(*items):
            return np.concatenate(items, axis=axis)
    else:
        structures = keras.tree.map_structure(keras.ops.convert_to_tensor, structures)

        def concat(*items):
            return keras.ops.concatenate(items, axis=axis)

    return keras.tree.map_structure(concat, *structures)


def concatenate(*tensors: Sequence[Tensor], axis=0):
    """Concatenate multiple tensors along axis, some of which can be None."""
    return keras.ops.concatenate([t for t in tensors if t is not None], axis=axis)


def tree_stack(structures: Sequence[T], axis: int = 0, numpy: bool = None) -> T:
    """Like :func:`tree_concatenate`, except tensors are stacked instead of concatenated."""
    if numpy is None:
        numpy = not any(keras.tree.flatten(keras.tree.map_structure(keras.ops.is_tensor, structures)))

    if numpy:
        structures = keras.tree.map_structure(keras.ops.convert_to_numpy, structures)

        def stack(*items):
            return np.stack(items, axis=axis)
    else:
        structures = keras.tree.map_structure(keras.ops.convert_to_tensor, structures)

        def stack(*items):
            return keras.ops.stack(items, axis=axis)

    return keras.tree.map_structure(stack, *structures)


def searchsorted(sorted_sequence: Tensor, values: Tensor, side: str = "left") -> Tensor:
    """
    Find indices where elements should be inserted to maintain order.
    """

    match keras.backend.backend():
        case "jax":
            import jax
            import jax.numpy as jnp

            logging.warn_once(f"searchsorted is not yet optimized for backend {keras.backend.backend()!r}")

            # do not vmap over the side argument (we have to pass it as a positional argument)
            in_axes = [0, 0, None]

            # vmap over the batch dimension
            vss = jax.vmap(jnp.searchsorted, in_axes=in_axes)

            # flatten all batch dimensions
            ss = sorted_sequence.reshape((-1,) + sorted_sequence.shape[-1:])
            v = values.reshape((-1,) + values.shape[-1:])

            # noinspection PyTypeChecker
            indices = vss(ss, v, side)

            # restore the batch dimensions
            indices = indices.reshape(values.shape)

            # noinspection PyTypeChecker
            return indices
        case "tensorflow":
            import tensorflow as tf

            # always use int64 to avoid complicated graph code
            indices = tf.searchsorted(sorted_sequence, values, side=side, out_type="int64")

            return indices
        case "torch":
            import torch

            out_int32 = len(sorted_sequence) <= np.iinfo(np.int32).max

            indices = torch.searchsorted(sorted_sequence, values, side=side, out_int32=out_int32)

            return indices
        case _:
            raise NotImplementedError(f"Searchsorted not implemented for backend {keras.backend.backend()!r}")
