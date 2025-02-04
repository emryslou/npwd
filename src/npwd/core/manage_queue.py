from queue import Queue
from typing import Any, Dict, Tuple, Callable
from threading import Event
from time import time

class ManageQueue(object):
    def __init__(self, *args: Tuple[str], **kwargs: Dict[str, int]):
        self.__start_time = time()
        self.__checkpoint_time = self.__start_time
        self.__queue_event = Event()
        self.__queues: Dict[str, Queue] = {
            arg: Queue(maxsize=int(kwargs.get(arg, 0)))
            for arg in args
        }

    def put(self, queue_name: str, item: Any, block: bool = True, timeout: float | None = None):
        try:
            self.__queues[queue_name].put(item=item, block=block, timeout=timeout)
        finally:
            self.update_checkpoint(queue_name)

    def put_nowait(self, queue_name: str, item: Any):
        try:
            self.put(queue_name, item, block=False)
        finally:
            self.update_checkpoint(queue_name)
    
    def get(self, queue_name: str, block: bool = True, timeout: float | None = None) -> Any:
        return self.__queues[queue_name].get(block=block, timeout=timeout)
    
    def get_nowait(self, queue_name: str) -> Any:
        return self.get(queue_name, block=False)
    
    def task_done(self, queue_name: str):
        return self.__queues[queue_name].task_done()
    
    def join(self, queue_name: str):
        return self.__queues[queue_name].join()
    
    def empty(self, queue_name: str):
        return self.__queues[queue_name].empty()

    def full(self, queue_name: str):
        return self.__queues[queue_name].full()
    
    def qsize(self, queue_name: str):
        return self.__queues[queue_name].qsize()
    
    def all_join(self):
        for _, q in self.__queues.items():
            q.join()
    
    def queue(self, queue_name: str) -> Queue:
        return self.__queues[queue_name]
    
    def stop(self):
        self.__queue_event.set()
    
    def running(self) -> bool:
        return not self.__queue_event.is_set()
    
    def idle(self, timeout: float = 15) -> bool:
        return time() - self.__checkpoint_time >= timeout
    
    def update_checkpoint(self, queue_name: str):
        if queue_name != 'progress':
            self.__checkpoint_time = time()
    
    @property
    def start_time(self):
        return self.__start_time