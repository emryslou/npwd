from typing import Any, Type, Optional, List


class ProviderNotFound(Exception):
    pass


class Provider(object):
    name: str

    plugins: List[Type["Provider"]] = []

    def __init_subclass__(cls, *args: Any, **kwargs: Any) -> None:
        super().__init_subclass__(*args, **kwargs)
        cls.plugins.append(cls)

    def chat(self, **kwargs):
        raise NotImplementedError('Todo ...')
