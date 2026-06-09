class Workflow:
    """
    Antigravity Workflow Orchestrator
    """
    def __init__(self, name: str):
        self.name = name
        self.steps = []

    def add_step(self, step_func):
        self.steps.append(step_func)
        return self

    def run(self, *args, **kwargs):
        results = []
        for step in self.steps:
            res = step(*args, **kwargs)
            results.append(res)
        return results
