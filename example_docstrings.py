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
        config (dict): Configuration dictionary containing model settings. See https://docs.ultralytics.com/modes/train for more details on available configuration options and parameters.
    """
    pass


def mixed_content(params):
    """Test mixed inline code and URLs.

    Args:
        params (dict): Pass `params={'conf': 0.5}` to adjust confidence or see https://docs.ultralytics.com for full options.
    """
    pass


def multiline_continuation(model, data, epochs):
    """Test multiline parameter descriptions.

    Args:
        model (nn.Module): PyTorch model instance that will be trained using the provided data and configuration settings.
        data (str): Path to dataset YAML file containing train/val splits and class names for training.
        epochs (int): Number of training epochs to run, with checkpoints saved at regular intervals throughout.
    """
    pass


class ExampleClass:
    """Test class docstring formatting.

    Attributes:
        name (str): Instance name identifier.
        callback (Callable[[int], bool]): Callback with bracket types.
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
