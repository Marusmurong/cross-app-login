"""
用户中心SDK的断路器实现
用于防止在服务不可用时持续发送请求
"""

import threading
import time
import logging
from typing import Dict, Optional, Callable, Any

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    断路器模式实现
    用于在服务不可用时停止发送请求，防止级联故障
    """

    # 断路器的可能状态
    STATE_CLOSED = "CLOSED"  # 正常工作状态
    STATE_OPEN = "OPEN"      # 断开状态，不允许请求通过
    STATE_HALF_OPEN = "HALF_OPEN"  # 半开状态，允许部分请求通过以测试服务是否恢复

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 3,
    ):
        """
        初始化断路器

        Args:
            name: 断路器名称
            failure_threshold: 触发断路器的连续失败次数阈值
            recovery_timeout: 断路器打开后尝试恢复的超时时间（秒）
            half_open_max_calls: 半开状态下允许的最大请求数
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        # 断路器状态
        self.state = self.STATE_CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
        self.lock = threading.RLock()
        self.total_successful_calls = 0
        self.total_failed_calls = 0
        self.total_blocked_calls = 0
        self.last_state_change_time = time.time()

    def allow_request(self) -> bool:
        """
        检查是否允许请求通过断路器

        Returns:
            是否允许请求通过
        """
        with self.lock:
            current_time = time.time()
            
            if self.state == self.STATE_CLOSED:
                # 闭合状态，允许请求通过
                return True
            
            elif self.state == self.STATE_OPEN:
                # 打开状态，检查是否已达到恢复超时时间
                if current_time - self.last_failure_time > self.recovery_timeout:
                    # 转为半开状态
                    self._transition_to_half_open()
                    return True
                else:
                    # 阻止请求通过
                    self.total_blocked_calls += 1
                    return False
            
            elif self.state == self.STATE_HALF_OPEN:
                # 半开状态，允许有限数量的请求通过
                if self.half_open_calls < self.half_open_max_calls:
                    self.half_open_calls += 1
                    return True
                else:
                    # 达到半开状态最大请求数，阻止请求通过
                    self.total_blocked_calls += 1
                    return False
            
            # 默认允许请求通过
            return True

    def record_success(self) -> None:
        """
        记录成功的请求
        """
        with self.lock:
            self.total_successful_calls += 1
            
            if self.state == self.STATE_HALF_OPEN:
                # 在半开状态下成功，转为闭合状态
                self._transition_to_closed()
            
            # 在闭合状态下，重置失败计数
            if self.state == self.STATE_CLOSED:
                self.failure_count = 0

    def record_failure(self) -> None:
        """
        记录失败的请求
        """
        with self.lock:
            self.total_failed_calls += 1
            self.last_failure_time = time.time()
            
            if self.state == self.STATE_HALF_OPEN:
                # 在半开状态下失败，转为打开状态
                self._transition_to_open()
            
            elif self.state == self.STATE_CLOSED:
                # 在闭合状态下，增加失败计数
                self.failure_count += 1
                
                # 如果达到失败阈值，转为打开状态
                if self.failure_count >= self.failure_threshold:
                    self._transition_to_open()

    def get_state(self) -> str:
        """
        获取断路器当前状态

        Returns:
            断路器当前状态
        """
        with self.lock:
            return self.state

    def reset(self) -> None:
        """
        重置断路器到闭合状态
        """
        with self.lock:
            self._transition_to_closed()

    def force_open(self) -> None:
        """
        强制将断路器设为打开状态
        """
        with self.lock:
            self._transition_to_open()

    def get_metrics(self) -> Dict[str, Any]:
        """
        获取断路器的统计指标

        Returns:
            断路器的统计指标
        """
        with self.lock:
            current_time = time.time()
            
            return {
                "name": self.name,
                "state": self.state,
                "failure_count": self.failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "half_open_calls": self.half_open_calls,
                "half_open_max_calls": self.half_open_max_calls,
                "total_successful_calls": self.total_successful_calls,
                "total_failed_calls": self.total_failed_calls,
                "total_blocked_calls": self.total_blocked_calls,
                "last_failure_time": self.last_failure_time,
                "last_state_change_time": self.last_state_change_time,
                "time_in_current_state": current_time - self.last_state_change_time,
                "remaining_recovery_time": max(0, self.recovery_timeout - (current_time - self.last_failure_time)) if self.state == self.STATE_OPEN else 0,
            }

    def _transition_to_closed(self) -> None:
        """
        将断路器转为闭合状态
        """
        logger.info(f"断路器 [{self.name}] 转为闭合状态")
        self.state = self.STATE_CLOSED
        self.failure_count = 0
        self.half_open_calls = 0
        self.last_state_change_time = time.time()

    def _transition_to_open(self) -> None:
        """
        将断路器转为打开状态
        """
        logger.warning(f"断路器 [{self.name}] 转为打开状态，已连续失败 {self.failure_count} 次")
        self.state = self.STATE_OPEN
        self.half_open_calls = 0
        self.last_state_change_time = time.time()

    def _transition_to_half_open(self) -> None:
        """
        将断路器转为半开状态
        """
        logger.info(f"断路器 [{self.name}] 转为半开状态，开始测试服务是否已恢复")
        self.state = self.STATE_HALF_OPEN
        self.half_open_calls = 0
        self.last_state_change_time = time.time()


def circuit_breaker(breaker: CircuitBreaker) -> Callable:
    """
    断路器装饰器，用于保护函数调用
    
    Args:
        breaker: 断路器实例
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            if not breaker.allow_request():
                raise RuntimeError(f"断路器 [{breaker.name}] 打开，请求被阻止")
            
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise e
                
        return wrapper
    return decorator


class CircuitBreakerRegistry:
    """
    断路器注册表，用于管理多个断路器实例
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CircuitBreakerRegistry, cls).__new__(cls)
                cls._instance._breakers = {}
        return cls._instance
    
    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 3,
    ) -> CircuitBreaker:
        """
        获取或创建断路器
        
        Args:
            name: 断路器名称
            failure_threshold: 触发断路器的连续失败次数阈值
            recovery_timeout: 断路器打开后尝试恢复的超时时间（秒）
            half_open_max_calls: 半开状态下允许的最大请求数
            
        Returns:
            断路器实例
        """
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    half_open_max_calls=half_open_max_calls,
                )
            return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """
        获取断路器
        
        Args:
            name: 断路器名称
            
        Returns:
            断路器实例，如果不存在则返回None
        """
        with self._lock:
            return self._breakers.get(name)
    
    def reset_all(self) -> None:
        """
        重置所有断路器
        """
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()
    
    def get_all_states(self) -> Dict[str, str]:
        """
        获取所有断路器的状态
        
        Returns:
            所有断路器的状态
        """
        with self._lock:
            return {name: breaker.get_state() for name, breaker in self._breakers.items()}
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有断路器的统计指标
        
        Returns:
            所有断路器的统计指标
        """
        with self._lock:
            return {name: breaker.get_metrics() for name, breaker in self._breakers.items()}
