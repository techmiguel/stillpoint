"""Escenarios canónicos de regresión. Cada uno reproduce un fallo conocido de
los sensores comerciales (docs/00) y se usa en tests y en las gráficas."""
from __future__ import annotations

from .config import Room
from .sim import Fan, Person, Scene


def occlusion(seed: int = 1):
    """B sentado quieto; A entra, se queda 12 s tapando su línea de visión y sale.
    Esperado: recuento 1 -> 2 -> 1, B nunca desaparece."""
    room = Room()
    B = Person([(0, 0.7, 0.0, "sitting"), (90, 0.7, 0.0, "sitting")], breath_hz=0.22)
    A = Person([(0, 3.5, 0, "standing"), (20, 3.5, 0, "standing"), (21, 1.9, 0, "standing"),
                (24, 0.35, 0, "standing"), (36, 0.35, 0, "standing"), (39, 1.9, 0, "standing"),
                (40, 3.5, 0, "standing"), (90, 3.5, 0, "standing")], breath_hz=0.3)
    truth = lambda t: (1 if t < 21 else 2 if t < 39.5 else 1)  # noqa: E731
    return Scene(room=room, people=[B, A], seed=seed), 70.0, truth


def fan_empty(seed: int = 2):
    """Sala vacía con ventilador. Esperado: 0 tras el aprendizaje (<= 20 s)."""
    return Scene(room=Room(), people=[], fans=[Fan(-1.2, 0.8)], seed=seed), 40.0, (lambda t: 0)


def mirror(seed: int = 3):
    """Una persona camina junto a una pared especular (espejo/armario)."""
    room = Room()
    A = Person([(0, -1.5, -1.0, "standing"), (8, 1.4, -1.0, "standing"), (16, -1.5, 1.0, "standing")])
    return Scene(room=room, people=[A], mirror_wall_x=2.0, seed=seed), 16.0, (lambda t: 1)


def fall(seed: int = 4, height: float = 1.75):
    """Camina, se cae a los 8 s y queda en el suelo."""
    A = Person([(0, -1.2, 0.5, "standing"), (7, 0.3, 0.2, "standing"), (8, 0.3, 0.2, "lying"),
                (30, 0.3, 0.2, "lying")], transition_s=0.8, fall_times=[7.2], height=height)
    return Scene(room=Room(), people=[A], seed=seed), 25.0, (lambda t: 1)


ALL = {"occlusion": occlusion, "fan_empty": fan_empty, "mirror": mirror, "fall": fall}
