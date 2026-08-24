import functools, time


def timed(func):
    # @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"{func.__name__} 耗时 {time.perf_counter() - t0:.2f}s")
        return result

    return wrapper


@timed
def slow_add(a, b):
    time.sleep(1)
    return a + b


print(slow_add(1,
               2))  # 观察输出顺序
print(slow_add.__name__)  # 有 wraps 是 'slow_add'，删掉 wraps 再看变成什么