from task_tracker import completion_rate, create_task, next_task


def test_create_task_accepts_priority_metadata() -> None:
    task = create_task("Ship README", priority=2)

    assert task["priority"] == 2
    assert task["done"] is False


def test_completion_rate_uses_done_field() -> None:
    tasks = [
        {"title": "write tests", "done": True},
        {"title": "record demo", "done": False},
    ]

    assert completion_rate(tasks) == 0.5


def test_next_task_handles_empty_backlog() -> None:
    assert next_task([]) is None
