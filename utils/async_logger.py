"""
Асинхронное логирование для улучшения производительности
"""
import asyncio
import logging
import threading
from queue import Queue
from typing import Optional


class AsyncLogHandler(logging.Handler):
    """Асинхронный обработчик логов для высоких нагрузок"""
    
    def __init__(self, base_handler: logging.Handler):
        super().__init__()
        self.base_handler = base_handler
        self.log_queue = Queue()
        self.running = True
        
        # Запускаем фоновый поток для записи логов
        self.log_thread = threading.Thread(target=self._log_worker, daemon=True)
        self.log_thread.start()
    
    def emit(self, record):
        """Добавить запись в очередь для асинхронной обработки"""
        if self.running:
            self.log_queue.put(record)
    
    def _log_worker(self):
        """Фоновый поток для записи логов"""
        while self.running:
            try:
                record = self.log_queue.get(timeout=1)
                if record is None:  # Сигнал завершения
                    break
                self.base_handler.emit(record)
                self.log_queue.task_done()
            except:
                # Игнорируем ошибки в фоновом потоке
                pass
    
    def close(self):
        """Закрыть обработчик"""
        self.running = False
        self.log_queue.put(None)  # Сигнал завершения
        self.log_thread.join(timeout=5)
        self.base_handler.close()
        super().close()


def setup_async_logging():
    """Настроить асинхронное логирование"""
    # Получить root logger
    root_logger = logging.getLogger()
    
    # Заменить обработчики на асинхронные версии
    for handler in root_logger.handlers[:]:
        async_handler = AsyncLogHandler(handler)
        async_handler.setLevel(handler.level)
        async_handler.setFormatter(handler.formatter)
        
        root_logger.removeHandler(handler)
        root_logger.addHandler(async_handler)