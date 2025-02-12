from typing import Callable, Any
from enum import Enum, IntEnum


class ProgressMetaType(Enum):
    FILE = pow(2, 0)
    LINE = pow(2, 1)
    INFO = pow(2, 2)
    LOG = pow(2, 3)
    IDLE = pow(2, 4)
    BATCH_DONE = pow(2, 5)


class ProgressMetaTotal(IntEnum):
    File = 3
    Line = 3


class ProgressMetaFileStatus(Enum):
    Recived = 0
    Queued = 1
    Processed = 2
    Succeed = 3
    Failure = 3


class ProgressMetaLineStatus(Enum):
    Created = 0
    Queued = 1
    Processed = 2
    Succeed = 3
    Failure = 3


def create_progress_meta(
        meta_type: ProgressMetaType,
        data: str = None, parent: str = None,
        total: int | None = None,
        status: str | ProgressMetaLineStatus | ProgressMetaFileStatus | None = None,
        message: str | None = None,
        result: Any = None,
        batch_id: str | None = None
) -> dict:
    return {
        'type': meta_type.value,
        'data': data,
        'parent': parent or '',
        'total': total,
        'status': str(status) or '',
        'message': message,
        'result': result,
        'batch_id': batch_id,
    }


class TaskManage(object):
    def __init__(self, progress, mq):
        self.progress = progress
        self.mq = mq
        self.__tasks = {}

    def create(self, key: str, total: int | str, color: str, parent: str | None = None):
        self.__tasks[key] = {
            'task': self.progress.add_task(f'[{color}]{key}', total=total),
            'parent': parent,
            'total': total,
        }

    def update(self, key: str, on_done: Callable | None = None, on_err: Callable | None = None):
        update_keys = [key]
        if self.__tasks[key]['parent']:
            update_keys.append(self.__tasks[key]['parent'])

        for _key in update_keys:
            try:
                if self.__tasks[_key]['total'] is None:
                    raise
                self.__tasks[_key]['total'] -= 1
                self.progress.update(self.__tasks[_key]['task'], advance=1)
                if self.__tasks[_key]['total'] <= 0:
                    self.progress.remove_task(self.__tasks[_key]['task'])
                    del self.__tasks[_key]
                    if on_done: on_done(_key)
            except BaseException as be:
                import traceback
                trace = traceback.format_exc()
                if on_err:
                    on_err(err=be, trace=trace, params={'task_key': _key, 'tasks': self.__tasks.copy()})

    def find(self, key: str) -> bool:
        return key in self.__tasks.keys()


def send_mq(mq, q: str, item: Any):
    mq.put_nowait(q, item)


def send_progress_meta(mq, **kwargs):
    import json
    from ..core import config

    if not config.get('with_progress', False):
        return

    message = kwargs.get('message', None)
    if kwargs['meta_type'] != ProgressMetaType.INFO and message:
        del kwargs['message']
        send_mq(mq, q='progress', item={
            'type': ProgressMetaType.INFO.value,
            'message': message,
            'batch_id': None,
        })
    send_mq(mq, q='progress', item=create_progress_meta(**kwargs))


def send_progress_msg(q, message: str):
    send_progress_meta(
        q, meta_type=ProgressMetaType.INFO, message=message
    )


def count_lines_of_file(file: str) -> int:
    with open(file, encoding='utf-8') as f:
        return len(f.readlines())


def progress_total(data: str, meta_type: ProgressMetaType) -> int:
    match meta_type:
        case ProgressMetaType.FILE:
            # ProgressMetaTotal.FILE + file_line_count * ProgressMetaTotal.LINE - 1
            return 3 + count_lines_of_file(data) * 3 - 1
        case ProgressMetaType.LINE:
            return 3  # ProgressMetaTotal.LINE
        case _:
            return 0
