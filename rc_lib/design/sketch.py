"""Defines entities which look like Onshape sketch entities.
"""

from typing import Callable, Self, cast
import abc
import enum

import manim as mn

from rc_lib.math_utils import vector
from rc_lib.style import color, animation


class SketchState(color.Color, enum.Enum):
    NORMAL = color.Palette.BLUE.value
    CONSTRAINED = color.Palette.BLACK.value
    ERROR = color.Palette.RED.value


class Base(mn.VMobject, abc.ABC):
    """An abstract base class for Sketch entities."""

    state = SketchState.NORMAL

    @abc.abstractmethod
    def create(self) -> mn.Animation:
        raise NotImplementedError

    @abc.abstractmethod
    def uncreate(self) -> mn.Animation:
        raise NotImplementedError


class Point(mn.Dot, Base):
    """Defines a singlar Sketch vertex."""

    def __init__(self, dot: mn.Dot) -> None:
        super().__init__()
        self.become(dot)

    def follow(self, point_function: Callable[[], vector.Point2d]) -> None:
        """Adds an updater function which causes this point to track the specified input."""

        def updater(mobject: mn.Mobject):
            mobject.move_to(point_function())

        self.add_updater(updater)

    def create(self) -> mn.Animation:
        return mn.Create(self, run_time=0)

    def uncreate(self) -> mn.Animation:
        return mn.Create(self, reverse_rate_function=True, remover=True, run_time=0)


def make_point(point: vector.Point2d) -> Point:
    return Point(mn.Dot(point, color=SketchState.NORMAL))


class Circle(mn.Circle, Base):
    """Defines a Sketch circle with a vertex at its center."""

    def __init__(self, circle: mn.Circle):
        super().__init__()
        self.become(circle)
        self.radius = circle.radius

        self.middle = make_point(self.get_center())
        self.middle.follow(self.get_center)

    def set_radius(self, radius: float) -> Self:
        self.scale(radius / self.radius)
        self.radius = radius
        return self

    def create(self) -> mn.Animation:
        return mn.Succession(
            mn.Create(self.middle, run_time=0), mn.GrowFromCenter(self)
        )

    def uncreate(self) -> mn.Animation:
        return mn.Succession(animation.ShrinkToCenter(self), self.middle.uncreate())


class Line(mn.Line, Base):
    """Defines a Sketch line segment vertices at each end."""

    def __init__(self, line: mn.Line) -> None:
        super().__init__()
        self.become(line)
        self.start = make_point(self.get_start())
        # instantiate end at start so it plays correctly
        self.end = make_point(self.get_end())

        self.start.follow(self.get_start)
        self.end.follow(self.get_end)

    def get_length(self) -> float:
        return vector.norm(self.get_end() - self.get_start())

    def get_direction(self) -> vector.Direction2d:
        return vector.normalize(self.get_end() - self.get_start())

    def move_start(self, point: vector.Point2d) -> Self:
        return self.put_start_and_end_on(point, self.get_end())  # type: ignore
        # return self.move_point(point, LineEnd.START)

    def move_end(self, point: vector.Point2d) -> Self:
        return self.put_start_and_end_on(self.get_start(), point)  # type: ignore

    def create(self) -> mn.Animation:
        return mn.Succession(self.start.create(), self.end.create(), mn.Create(self))

    def uncreate(self) -> mn.Animation:
        return mn.Succession(
            mn.Uncreate(self), self.start.uncreate(), self.end.uncreate()
        )


class Arc(mn.Arc, Base):
    """Defines a Sketch arc with vertices at each end and a vertex in the center."""

    def __init__(self, arc: mn.Arc) -> None:
        super().__init__()
        self.become(arc)
        self.radius = arc.radius

        self.start = make_point(self.get_start())
        self.end = make_point(self.get_end())
        # center is already a function...
        self.middle = make_point(self.get_arc_center())

        self.start.follow(self.get_start)
        self.end.follow(self.get_end)
        self.middle.follow(self.get_arc_center)

    def get_center(self) -> vector.Point2d:
        return self.middle.get_center()

    def set_radius(self, radius: float) -> Self:
        self.scale(radius / self.radius)
        self.radius = radius
        return self

    def create(self) -> mn.Animation:
        return mn.Succession(
            mn.Create(mn.VGroup(self.middle, self.start, self.end), run_time=0),
            mn.GrowFromCenter(self),
        )

    def uncreate(self) -> mn.Animation:
        return mn.Succession(
            animation.ShrinkToCenter(self),
            self.middle.uncreate(),
            self.start.uncreate(),
            self.end.uncreate(),
        )


class SketchFactory:
    """A factory for Sketch objects."""

    _color = SketchState.NORMAL

    def make_line(self, start_point: vector.Point2d, end_point: vector.Point2d) -> Line:
        return Line(mn.Line(start_point, end_point, color=self._color))

    def make_circle(self, center: vector.Point2d, radius: float) -> Circle:
        return Circle(mn.Circle(radius, color=self._color).move_to(center))

    def make_arc(
        self, center: vector.Point2d, radius: float, start_angle: float, angle: float
    ) -> Arc:
        return Arc(
            # start_angle is typed incorrectly as int
            mn.Arc(radius, start_angle=start_angle, angle=angle, color=self._color, arc_center=center)  # type: ignore
        )
