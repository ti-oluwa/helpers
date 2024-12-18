import typing
import random

T = typing.TypeVar("T")


def fisher_yates_shuffle(items: typing.List[T]) -> typing.List[T]:
    """
    Shuffle a list of items using the Fisher-Yates algorithm (In-place).

    :param items: The list of items to shuffle.
    :return: The shuffled list.
    """
    n = len(items)
    for i in range(n - 1, 0, -1):
        j = random.randint(0, i)  # Random index between 0 and i
        items[i], items[j] = items[j], items[i]  # Swap items
    return items
