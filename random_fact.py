import random


def get_random_fact() -> str | None:
    """
    Получение одного факта из файла "facts.txt".
    """
    loaded_facts: list[str] = []

    with open("facts.txt", "r", encoding="utf-8") as f:
        for line in f:
            fact = line.strip()
            if len(fact) != 0:
                loaded_facts.append(fact)

    if len(loaded_facts) != 0:
        return random.choice(loaded_facts)
