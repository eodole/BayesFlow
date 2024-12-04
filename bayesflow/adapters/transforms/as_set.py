import numpy as np

from .elementwise_transform import ElementwiseTransform


class AsSet(ElementwiseTransform):
    """
        The `.as_set(["x", "y"])` transform indicates that both `x` and `y` are treated as sets.
    <<<<<<< HEAD
        That is, their values will be treated as *exchangable* such that they will imply the same inference regardless of
        the values' order. This would be useful in a linear regression context where we can index the observations in
        arbitrary order and always get the same regression line.
    =======
        That is, their values will be treated as *exchangable* such that they will imply
        the same inference regardless of the values' order.
        This is useful, for example, in a linear regression context where we can index
        the observations in arbitrary order and always get the same regression line.
    >>>>>>> b8b68757b0ae1a5f34bf656a837abbeb77e2ec62

        Useage:

        adapter = (
            bf.Adapter()
            .as_set(["x", "y"])
            )
    """

    def forward(self, data: np.ndarray, **kwargs) -> np.ndarray:
        return np.atleast_3d(data)

    def inverse(self, data: np.ndarray, **kwargs) -> np.ndarray:
        if data.shape[2] == 1:
            return np.squeeze(data, axis=2)

        return data
