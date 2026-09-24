"""Utilidades comunes del simulador."""
import random


def clamp(value, minimum, maximum):
    """Limita un valor al rango [minimum, maximum]."""
    return max(minimum, min(maximum, value))


class RandomWalk:
    """
    Valor que cambia poco a poco: en cada paso se mueve como maximo "step"
    hacia arriba o hacia abajo y nunca sale de su rango. Asi dos registros
    seguidos nunca tienen diferencias absurdas (seccion 46).
    """

    def __init__(self, minimum, maximum, step, start):
        self.minimum = minimum
        self.maximum = maximum
        self.step = step
        self.value = clamp(start, minimum, maximum)

    def next(self):
        self.value = clamp(self.value + random.uniform(-self.step, self.step), self.minimum, self.maximum)
        return self.value

    @classmethod
    def from_config(cls, spec):
        """Crea la variacion a partir de una tupla (minimo, maximo, paso, inicial) de config.py."""
        minimum, maximum, step, start = spec
        return cls(minimum, maximum, step, start)
