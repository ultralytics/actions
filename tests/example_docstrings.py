# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license
"""Example file for Python docstring formatter with various edge cases and Google-style examples."""


def simple_function():
    """This is a simple single-line docstring without proper capitalization or punctuation."""
    pass


def long_single_line():
    """This is a very long single-line docstring that exceeds 120 characters and should be wrapped into a multi-line Google-style format automatically."""
    pass


def basic_args():
    """
    Function with basic args.

    Args:
        x: Simple arg without type.
        y (int): Arg with type.
        z (str, optional): Optional arg with type.
    """
    pass


def complex_args():
    """
    Function with complex argument descriptions that need wrapping.

    Args:
        prediction (torch.Tensor | numpy.array): YOLO predictions with shape (N, 6) for (x1, y1, x2, y2, score, class) and this description is very long and should wrap to continuation lines.
        conf_thres (float | int, optional): Confidence threshold for filtering detections with default value of 0.25.
        iou_thres (float, optional): IoU threshold for non-maximum suppression algorithm.

    Returns:
        detections (list[torch.Tensor]): List of filtered detections after NMS of shape (N, 6).
        max_conf (float): Highest confidence value of remaining detections.
    """
    pass


def with_examples():
    """
    Perform non-maximum suppression (NMS) on prediction boxes.

    This function takes predictions and applies NMS to filter overlapping boxes.

    Args:
        prediction (torch.Tensor): Predictions with shape (N, 6).
        conf_thres (float): Confidence threshold.

    Returns:
        (list[torch.Tensor]): Filtered detections.

    Examples:
        Run NMS on predictions:

        ```python
        prediction = torch.rand(100, 6)
        results = non_max_suppression(prediction, 0.5, 0.45)
        print(len(results))
        ```
    """
    pass


def multiline_description():
    """
    A function with a multi-paragraph description.

    This is the first paragraph of the description which explains the basic functionality and purpose of this function in detail.

    This is a second paragraph that provides additional context and information about how the function should be used in practice.

    Args:
        x (int): First parameter.
        y (int): Second parameter.

    Returns:
        (int): Sum of parameters.
    """
    pass


class ExampleClass:
    """
    A YOLODetector class for performing object detection using YOLO models.

    This class encapsulates the functionality for loading a YOLO model, performing inference on images, and applying non-maximum suppression to the results.

    Attributes:
        model (torch.nn.Module): The loaded YOLO model.
        device (torch.device): The device (CPU or GPU) on which the model is loaded.
        class_names (list | dict[int, str]): Class names that the model can detect.
        conf_threshold (float): Confidence threshold for filtering detections.
        iou_threshold (float): IoU threshold for non-maximum suppression.

    Methods:
        load_model: Loads a YOLO model from the specified path.
        detect: Performs object detection on the input image.
        non_max_suppression: Applies NMS to the model's predictions.

    Examples:
        Load a YOLODetector instance:

        ```python
        detector = YOLODetector(model_path="yolov5s.pt", conf_thres=0.25, iou_thres=0.45)
        image = cv2.imread("image.jpg")
        detections = detector.detect(image)
        for det in detections:
            print(f"Detected {det['class']} with confidence {det['confidence']}")
        ```
    """

    def __init__(self, model_path, conf_thres=0.25):
        """Initialize the detector with model path and confidence threshold."""
        pass

    def method_with_args(self, x, y, z):
        """
        Process data with multiple parameters.

        Args:
            x (int): The first parameter that represents some value.
            y (str): The second parameter with a very long description that will need to wrap across multiple lines when formatted.
            z (list[float], optional): Optional parameter with default of None.

        Returns:
            result (dict): Dictionary containing processed results with keys 'success' and 'data'.

        Raises:
            ValueError: If x is negative.
            TypeError: If y is not a string.
        """
        pass


def with_yields():
    """
    Generator function that yields values.

    Args:
        n (int): Number of values to generate.

    Yields:
        (int): Sequential integers from 0 to n-1.

    Examples:
        Generate values:

        ```python
        for i in gen(5):
            print(i)
        ```
    """
    pass


def badly_formatted():
    """
    This is a badly indented docstring
    with inconsistent spacing
        and weird indentation
    that should be cleaned up.

    Args:
      x: parameter with bad indent
        y: another parameter

    Returns:
      something
    """
    pass


def already_perfect():
    """
    This docstring is already perfectly formatted.

    Args:
        x (int): First parameter.
        y (str): Second parameter with a description that fits perfectly within the line width limit.

    Returns:
        (bool): Success flag.
    """
    pass


async def async_function():
    """Async function with simple docstring."""
    pass


def no_docstring():
    pass


def empty_docstring():
    """"""
    pass


def type_hints_in_args(x: int, y: str = "default") -> bool:
    """
    Function using type hints.

    Args:
        x: Integer value (type hint in signature).
        y: String value with default.

    Returns:
        (bool): Always True.
    """
    return True
