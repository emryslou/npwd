from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.events import DirMovedEvent, DirDeletedEvent, DirModifiedEvent, DirCreatedEvent
from watchdog.events import FileMovedEvent, FileDeletedEvent, FileModifiedEvent, FileCreatedEvent, FileClosedNoWriteEvent, FileClosedEvent, FileOpenedEvent
import warnings
from .tools import func_name


class UrlInfo(object):
    __slots__ = ('url', 'handler', 'name', 'blocks', 'snap_full_page', 'source', 'src_idx', 'batch_id')

    def __init__(self, **kwargs):
        """
        params:
            name: str # name
            url: str # an url string
            handler: str # handler name
            blocks: List[Map[str, str]] # block css selectors, eg. [{"name": "name", "selector": "css selector"}]
            snap_full_page: bool # snap full page 
            source: str # source file
            src_idx: int # content line no at source file
        """

        for slot in self.__slots__:
            if slot in kwargs.keys():
                self.__setattr__(slot, kwargs.get(slot))
                del kwargs[slot]
        
        if not hasattr(self, 'name'):
            self.name = ''
        if not hasattr(self, 'handler'):
            self.handler = 'default'
        if not hasattr(self, 'blocks'):
            self.blocks = []
        
        if not hasattr(self, 'snap_full_page'):
            self.snap_full_page = len(self.blocks) == 0
        
        if kwargs:
            warnings.warn(f'Too many params {kwargs}')
    
    def __str__(self):
        return '{}{{name: {}, url: {}, handler: {}, blocks: {}, snap_full_page: {}}}'\
                .format(
                    'UrlInfo', self.name, self.url,
                    self.handler, self.blocks, self.snap_full_page
                )


def event_names():
    return [fn.replace('on_', '') for fn in dir(FileSystemEventHandler) if fn.startswith('on_')][1:]


class UrlSourceEventHandler(FileSystemEventHandler):
    """Logs all the events captured."""

    def __init__(self,  **kwargs) -> None:
        super().__init__()
        
        self.__event_callbacks: dict = { 
            event: callback
            for (event, callback) in kwargs.items()
            if event in event_names()
        }

    def on_moved(self, event: DirMovedEvent | FileMovedEvent) -> None:
        super().on_moved(event)
        self.__notify_callback(func_name(), event)

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        super().on_created(event)
        self.__notify_callback(func_name(), event)

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        super().on_deleted(event)
        self.__notify_callback(func_name(), event)

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        super().on_modified(event)
        self.__notify_callback(func_name(), event)

    def on_closed(self, event: FileClosedEvent) -> None:
        super().on_closed(event)
        self.__notify_callback(func_name(), event)

    def on_closed_no_write(self, event: FileClosedNoWriteEvent) -> None:
        super().on_closed_no_write(event)
        self.__notify_callback(func_name(), event)

    def on_opened(self, event: FileOpenedEvent) -> None:
        super().on_opened(event)
        self.__notify_callback(func_name(), event)
    
    def __notify_callback(self, event_func_name: str, event: FileSystemEvent):
        event_name = event_func_name.replace('on_', '')
        if event_name in self.__event_callbacks.keys():
            self.__event_callbacks[event_name](event)
