def create_task(title: str) -> dict:
    return {"title": title, "done": False}


def completion_rate(tasks: list[dict]) -> float:
    done_count = sum(1 for task in tasks if task["completed"])
    return done_count / len(tasks)


def next_task(tasks: list[dict]) -> str:
    sorted_tasks = sorted(tasks, key=lambda task: task["priority"])
    return sorted_tasks[0]["title"]
