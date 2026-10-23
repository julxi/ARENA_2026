# %%
import sys
from pathlib import Path

import einops as ein
import numpy as np
import torch as t
from torch import Tensor

# Make sure exercises are in the path
chapter = "chapter0_fundamentals"
section = "part0_prereqs"
root_dir = next(p for p in Path.cwd().parents if (p / chapter).exists())
exercises_dir = root_dir / chapter / "exercises"
section_dir = exercises_dir / section
if str(exercises_dir) not in sys.path:
    sys.path.append(str(exercises_dir))

from part0_prereqs import tests
from part0_prereqs.utils import display_array_as_img, display_soln_array_as_img

arr = np.load(section_dir / "numbers.npy")


### Exercises - einops operations (match images)

# %%
arr1 = ein.rearrange(arr, "b c h w -> c (b h) w")
display_array_as_img(arr1)

# %%
arr2 = ein.repeat(arr[0], "c h w -> c (2 h) w")
display_array_as_img(arr2)

# %%
arr3 = ein.repeat(arr[:2], "b c h w -> c (b h) (2 w)")
display_array_as_img(arr3)

# %%
arr4 = ein.repeat(arr[0], "c h w -> c (h 2) w")
display_array_as_img(arr4)

# %%
arr5 = ein.repeat(arr[0], "c h w -> h (c w)")
display_array_as_img(arr5)

# %%
arr6 = ein.repeat(arr, "(b1 b2) c h w -> c (b1 h) (b2 w)", b1=2)
display_array_as_img(arr6)

# %%
arr7 = ein.rearrange(arr[1], "c h w -> c w h")
display_array_as_img(arr7)

# %%
arr8 = ein.reduce(arr, "(b1 b2) c (h h2) (w w2) -> c (b1 h) (b2 w)", "max", b1=2, h2=2, w2=2)
display_array_as_img(arr8)


### Exercises - einops operations & broadcasting
# %%
def rearrange_1() -> Tensor:
    """Return the following tensor using only t.arange and einops.rearrange:

    [[3, 4],
     [5, 6],
     [7, 8]]
    """
    return ein.rearrange(t.arange(3, 9), "(c r) -> c r", r=2)


tests.test_rearrange_1(rearrange_1)


# %%
def rearrange_2() -> Tensor:
    """Return the following tensor using only t.arange and einops.rearrange:

    [[1, 2, 3],
     [4, 5, 6]]
    """
    return ein.rearrange(t.arange(1, 7), "(c r) -> c r", r=3)


tests.test_rearrange_2(rearrange_2)


# %%
def temperatures_average(temps: Tensor) -> Tensor:
    """Return the average temperature for each week.

    temps: a 1D temperature containing temperatures for each day.
    Length will be a multiple of 7 and the first 7 days are for the first week, second 7 days for the second week, etc.

    You can do this with a single call to reduce.
    """
    assert len(temps) % 7 == 0
    return ein.reduce(temps, "(w d) -> w", "mean", d=7)


tests.test_temperatures_average(temperatures_average)


# %%
def temperatures_differences(temps: Tensor) -> Tensor:
    """For each day, subtract the average for the week the day belongs to.

    temps: as above
    """
    t_avg = ein.repeat(temperatures_average(temps), "w -> (w 7)")
    return temps - t_avg


tests.test_temperatures_differences(temperatures_differences)


# %%
def temperatures_normalized(temps: Tensor) -> Tensor:
    """For each day, subtract the weekly average and divide by the weekly standard deviation.

    temps: as above

    Pass t.std to reduce.
    """
    t_avg = temperatures_average(temps)
    t_sd = ein.reduce(temps, "(w 7) -> w", t.std)

    return (temps - ein.repeat(t_avg, "w -> (w 7)")) / ein.repeat(t_sd, "w -> (w 7)")


tests.test_temperatures_normalized(temperatures_normalized)


# %%
def normalize_rows(matrix: Tensor) -> Tensor:
    """Normalize each row of the given 2D matrix.

    matrix: a 2D tensor of shape (m, n).

    Returns: a tensor of the same shape where each row is divided by its l2 norm.
    """
    return matrix / t.norm(matrix, dim=-1, keepdim=True)


tests.test_normalize_rows(normalize_rows)


# %%
def cos_sim_matrix(matrix: Tensor) -> Tensor:
    """Return the cosine similarity matrix for each pair of rows of the given matrix.

    matrix: shape (m, n)
    """
    matrix_normalised = normalize_rows(matrix)
    return matrix_normalised @ matrix_normalised.T


tests.test_cos_sim_matrix(cos_sim_matrix)


# %%
def sample_distribution(probs: Tensor, n: int) -> Tensor:
    """Return n random samples from probs, where probs is a normalized probability distribution.

    probs: shape (k,) where probs[i] is the probability of event i occurring.
    n: number of random samples

    Return: shape (n,) where out[i] is an integer indicating which event was sampled.

    Use t.rand and t.cumsum to do this without any explicit loops.
    """

    cdf = t.cumsum(probs, dim=0)
    samples = t.rand(n)

    exceeds_cdf = samples.unsqueeze(-1) > cdf
    return exceeds_cdf.sum(dim=-1)


tests.test_sample_distribution(sample_distribution)


# %%
def classifier_accuracy(scores: Tensor, true_classes: Tensor) -> Tensor:
    """Return the fraction of inputs for which the maximum score corresponds to the true class for that input.

    scores: shape (batch, n_classes). A higher score[b, i] means that the classifier thinks class i is more likely.
    true_classes: shape (batch, ). true_classes[b] is an integer from [0...n_classes).

    Use t.argmax.
    """
    prediction = t.argmax(scores, dim=-1)
    return (prediction == true_classes).float().mean()


tests.test_classifier_accuracy(classifier_accuracy)


# %%
def total_price_indexing(prices: Tensor, items: Tensor) -> float:
    """Given prices for each kind of item and a tensor of items purchased, return the total price.

    prices: shape (k, ). prices[i] is the price of the ith item.
    items: shape (n, ). A 1D tensor where each value is an item index from [0..k).

    Use integer array indexing. The below document describes this for NumPy but it's the same in PyTorch:

    https://numpy.org/doc/stable/user/basics.indexing.html#integer-array-indexing
    """
    return prices[items].sum().item()


tests.test_total_price_indexing(total_price_indexing)


# %%
def gather_2d(matrix: Tensor, indexes: Tensor) -> Tensor:
    """Perform a gather operation along the second dimension.

    matrix: shape (m, n)
    indexes: shape (m, k)

    Return: shape (m, k). out[i][j] = matrix[i][indexes[i][j]]

    For this problem, the test already passes and it's your job to write at least three asserts relating the arguments and the output. This is a tricky function and worth spending some time to wrap your head around its behavior.

    See: https://pytorch.org/docs/stable/generated/torch.gather.html?highlight=gather#torch.gather
    """
    # YOUR CODE HERE - add assert statement(s) here for `indices` and `matrix`
    assert indexes.size(0) <= matrix.size(0)
    assert indexes.max() < matrix.size(1)

    out = matrix.gather(1, indexes)
    # YOUR CODE HERE - add assert statement(s) here for `out`
    assert out.shape == indexes.shape

    return out


tests.test_gather_2d(gather_2d)


# %%
def total_price_gather(prices: Tensor, items: Tensor) -> float:
    """Compute the same as total_price_indexing, but use torch.gather."""
    assert items.max() < prices.shape[0]

    item_prices = t.gather(prices, 0, items)
    return item_prices.sum().item()


tests.test_total_price_gather(total_price_gather)


# %%
def integer_array_indexing(matrix: Tensor, coords: Tensor) -> Tensor:
    """Return the values at each coordinate using integer array indexing.

    For details on integer array indexing, see:
    https://numpy.org/doc/stable/user/basics.indexing.html#integer-array-indexing

    matrix: shape (d_0, d_1, ..., d_n)
    coords: shape (batch, n)

    Return: (batch, )
    """
    return matrix[tuple(coords.T)]


tests.test_integer_array_indexing(integer_array_indexing)


# %%
def batched_logsumexp(matrix: Tensor) -> Tensor:
    """For each row of the matrix, compute log(sum(exp(row))) in a numerically stable way.

    matrix: shape (batch, n)

    Return: (batch, ). For each i, out[i] = log(sum(exp(matrix[i]))).

    Do this without using PyTorch's logsumexp function.

    A couple useful blogs about this function:
    - https://leimao.github.io/blog/LogSumExp/
    - https://gregorygundersen.com/blog/2020/02/09/log-sum-exp/
    """
    print("bathc", matrix.shape)
    row_max = t.max(matrix, dim=-1)[0]
    print(row_max.shape)
    t.exp(matrix - row_max).sum(dim=-1).log()


tests.test_batched_logsumexp(batched_logsumexp)
