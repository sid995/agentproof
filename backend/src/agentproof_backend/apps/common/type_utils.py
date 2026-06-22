"""Runtime helpers for type-checking compatibility."""

from typing import Any


def allow_runtime_generic(cls: type[Any]) -> None:
    """Allow non-generic runtime classes to be subscripted in typed class bases."""

    def __class_getitem__(
        inner_cls: type[Any],
        /,
        *_args: object,
        **_kwargs: object,
    ) -> Any:
        return inner_cls

    cls.__class_getitem__ = classmethod(__class_getitem__)
