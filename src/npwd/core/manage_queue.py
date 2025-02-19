from queue import Queue
from typing import Any, Dict, Tuple, Callable
from threading import Event
from time import time
import uuid
import json


class ManageQueue(object):
    """消息总线"""
    def __init__(self, *args: Tuple[str], **kwargs: Dict[str, int]):
        """初始化
        Args:
            *queue_names: Tuple[str]  # 队列名称
            **kwargs: Dict[str, int]  # 队列大小
        Example:
            ManageQueue('a', 'b', a=1, b=5)  # 消息总线，有两个队列: a, 队列大小: 1; b,  队列大小: 5
        """
        self.__start_time = time()
        self.__checkpoint_time = {
            arg: self.__start_time for arg in args
        }
        self.__queue_event = Event()
        self.__queues: Dict[str, Queue] = {
            arg: Queue(maxsize=int(kwargs.get(arg, 0)))
            for arg in args
        }
        self.__uuid_cache = None

    def put(self, queue_name: str, item: Any, block: bool = True, timeout: float | None = None) -> None:
        """入队
        Args:
            queue_name: str  # 队列名称
            item: Any  # 消息
            block: bool  # 可选，是否阻塞，默认：True
            timeout: float  # 可选，阻塞超时时间
        Return:
            None
        """
        try:
            self.__queues[queue_name].put(item=json.dumps(item), block=block, timeout=timeout)
        finally:
            self.update_checkpoint(queue_name)

    def put_nowait(self, queue_name: str, item: Any):
        """入队，不阻塞
        Args:
            queue_name: str  # 队列名称
            item: Any  # 消息
        Return:
            None
        """
        try:
            self.put(queue_name, item, block=False)
        finally:
            self.update_checkpoint(queue_name)
    
    def get(self, queue_name: str, block: bool = True, timeout: float | None = None) -> Any:
        """出队
        Args:
            queue_name: str  # 队列名称
            block: bool  # 可选，是否阻塞，默认：True
            timeout: float  # 可选，阻塞超时时间
        Return:
            Any
        """
        return json.loads(s=self.__queues[queue_name].get(block=block, timeout=timeout))
    
    def get_nowait(self, queue_name: str) -> Any:
        """出队，非阻塞
        Args:
            queue_name: str  # 队列名称
        Return:
            Any
        """
        return self.get(queue_name, block=False)
    
    def task_done(self, queue_name: str) -> None:
        """当前消息任务完成
        Args:
            queue_name: str  # 队列名称
        Return:
            None
        """
        return self.__queues[queue_name].task_done()
    
    def join(self, queue_name: str) -> None:
        """等待队列中所有任务完成
        Args:
            queue_name: str  # 队列名称
        Return:
            None
        """
        return self.__queues[queue_name].join()
    
    def empty(self, queue_name: str) -> bool:
        """队列是否为空
        Args:
            queue_name: str  # 队列名称
        Return:
            Bool
        """
        return self.__queues[queue_name].empty()

    def full(self, queue_name: str) -> bool:
        """队列是否满了
        Args:
            queue_name: str  # 队列名称
        Return:
            Bool
        """
        return self.__queues[queue_name].full()
    
    def qsize(self, queue_name: str) -> int:
        """队列大小
        Args:
            queue_name: str  # 队列名称
        Return:
            int
        """
        return self.__queues[queue_name].qsize()
    
    def all_join(self):
        """等待所有队列中所有任务完成"""
        for _, q in self.__queues.items():
            q.join()
    
    def queue(self, queue_name: str) -> Queue:
        """队列
        Args:
            queue_name: str  # 队列名称
        Return:
            Queue
        """
        return self.__queues[queue_name]
    
    def stop(self):
        """停止任务"""
        self.__queue_event.set()
    
    def running(self) -> bool:
        """任务是否在运行"""
        return not self.__queue_event.is_set()
    
    def idle(self, timeout: float = 15, q: str | None = None) -> bool:
        """队列大小
        Args:
            timeout: float  # 距离上次运行超过 多少 秒， 默认: 15
            q: str  # 队列名称，可选
        Return:
            bool
        """
        if q:
            return time() - self.__checkpoint_time[q] > timeout
        else:
            return time() - max([
                    _t for _q, _t in self.__checkpoint_time.items()
                    if _q != 'progress'
                ]) > timeout
    
    def update_checkpoint(self, queue_name: str) -> None:
        """更新检查点
        Args:
            queue_name: str  # 队列名称
        Return:
            bool
        """
        self.__checkpoint_time[queue_name] = time()
    
    @property
    def start_time(self):
        return self.__start_time
    
    def uuid(self, flush_cache: bool = False) -> str:
        if flush_cache or self.__uuid_cache is None:
            self.__uuid_cache = str(uuid.uuid5(uuid.NAMESPACE_DNS, 'tinystone.com'))
        return self.__uuid_cache
