"""Defines entities which look like Onshape sketch entities.
"""
from __future__ import annotations

from typing import Callable, Self, Any
from abc import ABC, abstractmethod
import enum

import manim as mn

from rc_lib.math_utils import vector
from rc_lib.style import color, animation
from rc_lib.design import constraint


class SketchState(color.Color, enum.Enum):
    NORMAL = color.Palette.BLUE.value
    CONSTRAINED = color.Palette.BLACK.value
    ERROR = color.Palette.RED.value


class Base(mn.VMobject, ABC):
    """An abstract base class for Sketch entities."""

    state = SketchState.NORMAL

    @abstractmethod
    def _create_override(self) -> mn.Animation:
        raise NotImplementedError

    @abstractmethod
    def _uncreate_override(self) -> mn.Animation:
        raise NotImplementedError

    @abstractmethod
    def coincident_target(self, point: vector.Point2d) -> mn.Animation:
        raise NotImplementedError


class ArcBase(Base, ABC):
    radius: float
    middle: Point

    def set_radius(self, radius: float) -> Self:
        self.scale(radius / self.radius)
        self.radius = radius
        return self

    @mn.override_animation(constraint.Equal)
    def _equal_override(self, target: Self) -> mn.Animation:
        return target.animate.set_radius(self.radius)  # type: ignore

    def coincident_target(self, point: vector.Point2d) -> vector.Point2d:
        return self.get_center() + (
            vector.direction(self.get_center(), point) * self.radius
        )

    def _get_circle_translation(self, target: Self) -> vector.Vector2d:
        vec = target.get_center() - self.get_center()
        return vector.normalize(vec) * (vector.norm(vec) - self.radius - target.radius)


class Point(mn.Dot, Base):
    """Defines a singlar Sketch vertex."""

    def __init__(self, dot: mn.Dot) -> None:
        super().__init__()
        self.become(dot)

    def follow(self, point_function: Callable[[], vector.Point2d]) -> Self:
        """Adds an updater function which causes this point to track the specified input."""

        def updater(mobject: mn.Mobject):
            mobject.move_to(point_function())

        self.add_updater(updater, call_updater=True)

        return self

    @mn.override_animation(constraint.Coincident)
    def _coincident_override(self, target: Base) -> Any:
        return self.animate.move_to(target.coincident_target(self.get_center()))

    def coincident_target(self, _: vector.Point2d) -> vector.Point2d:
        return self.get_center()

    @mn.override_animation(mn.Create)
    def _create_override(self) -> mn.Animation:
        return mn.Animation(self, introducer=True, run_time=0)

    @mn.override_animation(mn.Uncreate)
    def _uncreate_override(self) -> mn.Animation:
        return mn.Animation(self, introducer=True, remover=True, run_time=0)

    @mn.override_animation(constraint.Vertical)
    def _vertical_override(self, target: Point) -> mn.Animation:
        return self._align_override(target, constraint.AlignType.VERTICAL)

    @mn.override_animation(constraint.Horizontal)
    def _horizontal_override(self, target: Point) -> mn.Animation:
        return self._align_override(target, constraint.AlignType.HORIZONTAL)

    def _align_override(
        self, target: Point, type: constraint.AlignType
    ) -> mn.Animation:
        if type == constraint.AlignType.VERTICAL:
            values = (target, self)
        else:
            values = (self, target)

        target_point = vector.point_2d(
            values[0].get_center()[0], values[1].get_center()[1]
        )
        return mn.prepare_animation(self.animate.move_to(target_point))


class Line(mn.Line, Base):
    """Defines a Sketch line segment vertices at each end."""

    def __init__(self, line: mn.Line) -> None:
        super().__init__()
        self.become(line)

        self.start = _make_point(point=self.get_start())
        self.end = _make_point(point=self.get_end())

        def updater(mobject: mn.Mobject) -> None:
            mobject.put_start_and_end_on(self.start.get_center(), self.end.get_center())

        self.add_updater(updater)

    def get_length(self) -> float:
        return vector.norm(self.get_end() - self.get_start())

    def get_direction(self) -> vector.Direction2d:
        return vector.normalize(self.get_end() - self.get_start())

    def move_start(self, point: vector.Point2d) -> Self:
        self.start.move_to(point)
        return self

    def move_end(self, point: vector.Point2d) -> Self:
        self.end.move_to(point)
        return self

    @mn.override_animation(constraint.Vertical)
    def _vertical_override(self) -> mn.Animation:
        return self._align_override(constraint.AlignType.VERTICAL)

    @mn.override_animation(constraint.Horizontal)
    def _horizontal_override(self) -> mn.Animation:
        return self._align_override(constraint.AlignType.HORIZONTAL)

    def _align_override(self, type: constraint.AlignType) -> mn.Animation:
        curr_angle = self.get_angle()
        if type == constraint.AlignType.VERTICAL:
            if curr_angle >= 0 and curr_angle < mn.PI:
                angle = (mn.PI / 2) - curr_angle
            else:
                angle = -(mn.PI / 2) - curr_angle
        else:
            if curr_angle >= -mn.PI / 2 and curr_angle < mn.PI / 2:
                angle = -curr_angle
            else:
                angle = -mn.PI - curr_angle
        return mn.Rotate(mn.VGroup(self.start, self.end), angle=angle, about_point=self.get_midpoint())  # type: ignore

    @mn.override_animation(constraint.Equal)
    def _equal_override(self, target: Self) -> Any:
        midpoint = target.get_midpoint()
        offset = target.get_direction() * (self.get_length() / 2)
        return target.animate(suspend_mobject_updating=False).put_start_and_end_on(
            midpoint - offset, midpoint + offset
        )

    def coincident_target(self, point: vector.Point2d) -> vector.Point2d:
        return self.get_projection(point)

    @mn.override_animation(constraint.Tangent)
    def _tangent_override(self, target: ArcBase) -> Any:
        translation = self._get_line_translation(target)
        return (
            mn.VGroup(self.start, self.end)
            .animate(suspend_mobject_updating=False)
            .shift(translation)
        )

    def _get_line_translation(self, target: ArcBase) -> vector.Vector2d:
        projection: vector.Point2d = self.get_projection(target.get_center())  # type: ignore
        return vector.direction(projection, target.get_center()) * (
            vector.norm(target.get_center() - projection) - target.radius
        )

    @mn.override_animation(mn.Create)
    def _create_override(self) -> mn.Animation:
        end = self.get_end()
        return mn.Succession(
            constraint.Add(self.start, self.end, self),
            mn.prepare_animation(
                self.end.move_to(self.get_start() + vector.ZERO_LENGTH_VECTOR)
                .animate(suspend_mobject_updating=False)
                .move_to(end)
            ),
        )

    @mn.override_animation(mn.Uncreate)
    def _uncreate_override(self) -> mn.Animation:
        return mn.Succession(
            mn.prepare_animation(
                self.end.animate(suspend_mobject_updating=False).move_to(
                    self.get_start() + vector.ZERO_LENGTH_VECTOR
                )
            ),
            constraint.Remove(self.start, self.end, self),
        )


class Circle(mn.Circle, ArcBase):
    """Defines a Sketch circle with a vertex at its center."""

    def __init__(self, circle: mn.Circle):
        super().__init__()
        self.become(circle)
        self.radius = circle.radius
        self.arc_center = circle.arc_center

        # center is already used
        self.middle = _make_point(point=self.arc_center)

        def updater(mobject: mn.Mobject) -> None:
            mobject.move_to(self.middle.get_center())

        self.add_updater(updater)

    @mn.override_animation(constraint.Tangent)
    def _tangent_override(self, target: ArcBase) -> Any:
        translation = super()._get_circle_translation(target)  # type: ignore
        return self.middle.animate.shift(translation)

    @mn.override_animation(mn.Create)
    def _create_override(self) -> mn.Animation:
        return mn.Succession(
            constraint.Add(self.middle),
            mn.GrowFromCenter(self, suspend_mobject_updaters=False),
        )

    @mn.override_animation(mn.Uncreate)
    def _uncreate_override(self) -> mn.Animation:
        return mn.Succession(
            mn.GrowFromCenter(
                self,
                reverse_rate_function=True,
                remover=True,
                suspend_mobject_updaters=False,
            ),
            constraint.Remove(self.middle),
        )


class Arc(mn.Arc, ArcBase):
    """Defines a Sketch arc with vertices at each end and a vertex in the center."""

    def __init__(self, arc: mn.Arc) -> None:
        super().__init__()
        self.become(arc)
        self.radius = arc.radius
        self.arc_center = arc.arc_center

        self.start = _make_point().follow(self.get_start)
        self.end = _make_point().follow(self.get_end)

        # center is already used
        self.middle = _make_point(point=self.arc_center)

        def updater(mobject: mn.Mobject) -> None:
            mobject.move_arc_center_to(self.middle.get_center())
            self.start.update()
            self.end.update()

        self.add_updater(updater)

    def get_center(self) -> vector.Point2d:
        return self.middle.get_center()

    @mn.override_animation(constraint.Tangent)
    def _tangent_override(self, target: ArcBase) -> Any:
        translation = super()._get_circle_translation(target)  # type: ignore
        return self.middle.animate(suspend_mobject_updating=False).shift(translation)
        # return mn.Transform(group, group.copy().shift(translation))

    @mn.override_animation(mn.Create)
    def _create_override(self) -> mn.Animation:
        return mn.Succession(
            constraint.Add(self.start, self.end, self.middle),
            mn.GrowFromCenter(self, suspend_mobject_updaters=False),
        )

    @mn.override_animation(mn.Uncreate)
    def _uncreate_override(self) -> mn.Animation:
        return mn.Succession(
            mn.GrowFromCenter(
                self,
                reverse_rate_function=True,
                remover=True,
                suspend_mobject_updaters=False,
            ),
            constraint.Remove(self.start, self.end, self.middle),
        )


def _make_point(point: vector.Point2d = mn.ORIGIN) -> Point:
    return Point(mn.Dot(point, color=SketchState.NORMAL))


def make_line(start_point: vector.Point2d, end_point: vector.Point2d) -> Line:
    return Line(mn.Line(start_point, end_point, color=SketchState.NORMAL))


def make_circle(center: vector.Point2d, radius: float) -> Circle:
    return Circle(mn.Circle(radius, color=SketchState.NORMAL, arc_center=center))


def make_arc(
    center: vector.Point2d, radius: float, start_angle: float, angle: float
) -> Arc:
    return Arc(
        # start_angle is typed incorrectly as int
        mn.Arc(radius, start_angle=start_angle, angle=angle, color=SketchState.NORMAL, arc_center=center)  # type: ignore
    )
