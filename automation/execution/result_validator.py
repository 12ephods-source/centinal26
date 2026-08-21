"""Validate execution result records."""


def validate(result):
    required = ["task_id", "status", "timestamp"]
    return all(k in result for k in required)


if __name__ == "__main__":
    print("Result validator ready.")
