"""Small, local decision models: typed choices are hints, never source evidence."""
import math


def decision_model(name):
    name = str(name or '').rsplit('/', 1)[-1].casefold().removeprefix('kingfisher-')
    return name.split(':', 1)[0] in {'tev1', 'nimble'}


def read_choice(result, name, labels):
    """Conservative initial threshold; not a calibrated error probability for our corpus."""
    if not isinstance(result, dict) or not isinstance(result.get('answers'), dict):
        return None
    answers = result['answers']
    if set(answers) != {name} or not isinstance(answers[name], dict):
        return None
    answer = answers[name]
    choice, confidence, probabilities = answer.get('choice'), answer.get('confidence'), answer.get('probabilities')
    number = lambda n: type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1
    if (answer.get('type') != 'choice' or choice not in labels or not number(confidence)
            or confidence < .9 or not isinstance(probabilities, dict) or set(probabilities) != set(labels)
            or not all(number(p) for p in probabilities.values())
            or not math.isclose(sum(probabilities.values()), 1, abs_tol=.001)
            or probabilities[choice] < .9 or probabilities[choice] != max(probabilities.values())):
        return None
    return choice
