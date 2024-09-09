from django.db import models


class PostgreSQLArrayAppend(models.Func):
    """
    Custom function to append an element to a PostgreSQL array.

    Uses the `array_append` function in PostgreSQL.
    """
    function = "array_append"
    template = "%(function)s(%(expressions)s)"

    def __init__(self, *expressions, **extras):
        """
        Initialize the function with the expressions to append to the array.

        :param expressions: The expressions to append to the array. Should be two expressions.
        The first expression is the array field and the second is the element to append.
        :param extras: Extra arguments to pass to the `models.Func` constructor.

        Example:

        ```python
        from django.db import models
        from .models import MyModel

        MyModel.objects.update(
            array_field=PostgresArrayAppend(
                models.F('array_field'), models.Value('new_element')
            )
        )
        ```
        """
        if len(expressions) != 2:
            raise ValueError("Two expressions are required.")
        super().__init__(*expressions, **extras)


class PostgreSQLArrayRemove(models.Func):
    """
    Custom function to remove an element from a PostgreSQL array.

    Uses the `array_remove` function in PostgreSQL.
    """

    function = "array_remove"
    template = "%(function)s(%(expressions)s)"

    def __init__(self, *expressions, **extras):
        """
        Initialize the function with the expressions to remove from the array.

        :param expressions: The expressions to remove from the array. Should be two expressions.
        The first expression is the array field and the second is the element to remove.
        :param extras: Extra arguments to pass to the `models.Func` constructor.

        Example:

        ```python
        from django.db import models
        from .models import MyModel

        MyModel.objects.update(
            array_field=PostgresArrayRemove(
                models.F('array_field'), models.Value('element_to_remove')
            )
        )
        ```
        """
        if len(expressions) != 2:
            raise ValueError("Two expressions are required.")
        super().__init__(*expressions, **extras)
