import time
import functools

# Decorator to log execution time of a function

def log_execution_time(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"Executed {func.__name__!r} in {execution_time:.4f} secs")
        return result
    return wrapper
