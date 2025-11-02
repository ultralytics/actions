# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license
"""Test file for docstring formatter edge cases."""


def nested_brackets(callback):
    """Test nested brackets in type hints.

    Args:
        callback (Callable[[int, str], None]): Function with nested bracket type annotation that should not split.
    """
    pass


def inline_code_test(model):
    """Test inline code preservation.

    Args:
        model (object): Use `model.predict()` to run inference with the trained model instance.
    """
    pass


def url_test(endpoint):
    """Test URL preservation.

    Args:
        endpoint (str): The API endpoint URL like https://api.ultralytics.com/v1/predict for remote inference.
    """
    pass


def optional_type(x, y):
    """Test optional type syntax.

    Args:
        x (int, optional): First parameter with comma in type annotation.
        y (str, optional): Second parameter, also optional with default None value.
    """
    pass


def complex_types(data, transform):
    """Test complex type annotations.

    Args:
        data (dict[str, list[tuple[int, float]]]): Nested generic type that uses bracket syntax heavily.
        transform (Callable[[torch.Tensor], torch.Tensor] | None): Optional transform function or None.
    """
    pass


def long_description(config):
    """Test long description wrapping.

    Args:
        config (dict): Configuration dictionary containing model settings. See https://docs.ultralytics.com/modes/train
            for more details on available configuration options and parameters.
    """
    pass


def mixed_content(params):
    """Test mixed inline code and URLs.

    Args:
        params (dict): Pass `params={'conf': 0.5}` to adjust confidence or see https://docs.ultralytics.com for full
            options.
    """
    pass


def multiline_continuation(model, data, epochs, optimizer, scheduler):
    """Test multiline parameter descriptions.

    Args:
        model (nn.Module): PyTorch model instance that will be trained using the provided data and configuration
            settings for optimal performance.
        data (str): Path to dataset YAML file containing train/val splits and class names for training.
        epochs (int): Number of training epochs to run, with checkpoints saved at regular intervals throughout the
        entire training process to ensure model recovery. optimizer (torch.optim.Optimizer): Optimizer instance for
            gradient descent. Common choices include Adam, SGD, or AdamW with appropriate learning rates and weight
            decay parameters. Second set of common choices include Adam, SGD, or AdamW with appropriate learning rates
        and weight decay parameters. scheduler (torch.optim.lr_scheduler._LRScheduler | None): Learning rate scheduler
            for adaptive learning rate adjustment during training, or None to use constant learning rate.
    """
    pass


def no_args_function():
    """Test function with no arguments."""
    pass


def args_kwargs_function(*args, **kwargs):
    """Test function with variable arguments.

    Args:
        *args (Any): Variable positional arguments passed to the function for flexible parameter handling.
        **kwargs (Any): Variable keyword arguments for additional named parameters and configuration options.
    """
    pass


def generator_function(n):
    """Test function with Yields section.

    Args:
        n (int): Number of items to generate in sequence.

    Yields:
        (int): Sequential integers from 0 to n-1.

    Examples:
        Generate first 5 numbers
        >>> for i in generator_function(5):
        >>>     print(i)
    """
    yield from range(n)


def function_with_raises(x):
    """Test function with Raises section.

    Args:
        x (int): Input value that must be positive.

    Returns:
        (float): Square root of the input value.

    Raises:
        ValueError: If x is negative.
        TypeError: If x is not a number.
    """
    if x < 0:
        raise ValueError("x must be positive")
    return x**0.5


def function_with_notes(data):
    """Test function with Notes and Warnings.

    Args:
        data (list): Input data to process.

    Returns:
        (list): Processed data.

    Notes:
        This function modifies the input list in-place for memory efficiency. Consider passing a copy if you need to preserve the original data.

    Warnings:
        Performance may degrade with lists larger than 10000 elements. Use batch processing for large datasets.
    """
    return data


def comprehensive_docstring(x, y=None, *args, **kwargs):
    """Test function with all common sections.

    This function demonstrates a comprehensive docstring with all major sections including detailed descriptions and
    multiple examples.

    Args:
        x (int | float): Primary input value for computation. y (str, optional): Secondary parameter with default None.
        *args (Any): Additional positional arguments.
        **kwargs (Any): Additional keyword arguments like `verbose=True` for logging.

    Returns:
        result (dict): Dictionary containing:
            - value (float): Computed result.
            - status (str): Operation status.

    Raises:
        ValueError: If x is not within valid range [0, 100].
        RuntimeError: If computation fails unexpectedly.

    Examples:
        Basic usage with required argument
        >>> result = comprehensive_docstring(42)
        >>> print(result["value"])
        42.0

        Usage with optional parameters
        >>> result = comprehensive_docstring(10, y="test", verbose=True)
        >>> print(result["status"])
        'success'

    Notes:
        This function uses advanced algorithms for optimal performance. See https://docs.example.com/algorithms for implementation details.

    Warnings:
        Results may vary based on system precision and floating-point representation.
    """
    return {"value": float(x), "status": "success"}


def returns_none(x):
    """Test function returning None.

    Args:
        x (Any): Input value to log.

    Returns:
        (None): This function returns nothing.
    """
    print(x)
    return None


def multiple_return_types(x):
    """Test function with union return types.

    Args:
        x (int): Input value.

    Returns:
        (int | None): Returns processed value or None on failure.
    """
    return x if x > 0 else None


def union_and_optional_types(x, y=None):
    """Test union and optional type annotations.

    Args:
        x (int | float | str): Value accepting multiple types. y (list[int] | tuple[int, ...] | None, optional):
            Optional sequence with None default.

    Returns:
        (bool): Whether processing succeeded.
    """
    return True


def literal_types(mode):
    """Test literal type annotations.

    Args:
        mode (Literal['train', 'val', 'test']): Operation mode must be one of the specified literal values.

    Returns:
        (str): Confirmation message for selected mode.
    """
    return f"Mode: {mode}"


class ExampleClass:
    """Test class docstring formatting.

    Attributes:
        name (str): Instance name identifier. callback (Callable[[int], bool]): Callback with bracket types.
    """

    def method_with_returns(self, x):
        """Test returns section.

        Args:
            x (int): Input value to process.

        Returns:
            (tuple): Tuple containing:
                - result (int): Processed value.
                - status (bool): Success flag.
        """
        return x * 2, True

    def method_with_examples(self):
        """Test examples section preservation.

        Examples:
            ```python
            obj = ExampleClass()
            result = obj.method_with_examples()
            ```
        """
        pass

    @classmethod
    def class_method(cls, x):
        """Test classmethod docstring.

        Args:
            x (int): Value to initialize class with.

        Returns:
            (ExampleClass): New instance of the class.
        """
        instance = cls()
        instance.name = str(x)
        return instance

    @staticmethod
    def static_method(x, y):
        """Test staticmethod docstring.

        Args:
            x (int): First value.
            y (int): Second value.

        Returns:
            (int): Sum of x and y.
        """
        return x + y

    @property
    def computed_property(self):
        """This function uses advanced algorithms for optimal performance.

        See https://docs.example.com/algorithms for
        implementation details.
        """
        return f"Property: {self.name}"

    @property
    def computed_property_two(self):
        """This function uses advanced algorithms for optimal performance, See https://docs.example.com/algorithms for
        implementation details.
        """
        return f"Property: {self.name}"


if __name__ == "__main__":
    import os

    os.system("python actions/format_python_docstrings.py example_docstrings.py && git --no-pager diff -U999999")
