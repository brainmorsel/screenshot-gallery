from collections import namedtuple


MetaDataItem = namedtuple('MetaDataItem', 'method args kwargs')


class MetaCollector:
    def __init__(self, _items=None):
        self._items = _items or []

    def __call__(self, *args, **kwargs):
        def register(method):
            self._items.append(MetaDataItem(method, args, kwargs))
            return method
        return register

    def __iter__(self):
        return iter(self._items)

    def bind(self, instance):
        _items = []
        for method, args, kwargs in self._items:
            # bind method to instance (descriptors magic)
            method = method.__get__(instance)
            _items.append(MetaDataItem(method, args, kwargs))
        return MetaCollector(_items=_items)
