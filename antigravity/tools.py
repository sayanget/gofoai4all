def tool(name_or_func=None):
    """
    Antigravity tool decorator.
    Can be used as @tool or @tool("custom_name")
    """
    def decorator(func):
        func.is_tool = True
        func.tool_name = name_or_func if isinstance(name_or_func, str) else func.__name__
        return func

    if callable(name_or_func):
        # Used as @tool
        func = name_or_func
        func.is_tool = True
        func.tool_name = func.__name__
        return func
    
    return decorator
