from __future__ import annotations

import math
from typing import Union

import numpy as np

CoordinateType = Union[int, float, np.float64] # int | float | np.float64

class Point:
    x: CoordinateType
    y: CoordinateType

    def __init__(self, x: CoordinateType, y: CoordinateType) -> None:
        # print([param_type for param_type in [type(x), type(y)]])
        # assert all([param_type in [int, float, np.float64] for param_type in [type(x), type(y)]])
        assert all(isinstance(coord, CoordinateType) for coord in [x, y])
        self.x = x
        self.y = y

    def __str__(self) -> str:
        return f"({self.x}, {self.y})"

    # Allow iterate over atribute values (in this case, x and y)
    def __iter__(self) -> int:
        for value in self.__dict__.values():
            yield value

    def __add__(self, other: Point) -> Point:
        if isinstance(other, float) or isinstance(other, int):
            x = self.x + other
            y = self.y + other
        else:
            x = self.x + other.x
            y = self.y + other.y
        return Point(x, y)
    
    def __sub__(self, other: Point) -> Point:
        if isinstance(other, float) or isinstance(other, int):
            x = self.x - other
            y = self.y - other
        else:
            x = self.x - other.x
            y = self.y - other.y
        return Point(x, y)
    
    def __neg__(self):
        return Point(-self.x, -self.y)
    
    def __mul__(self, other) -> Point:
        return Point.__mul(other)
    
    def __rmul__(self, other) -> Point:
        return Point.__mul(self, other)

    @staticmethod
    def __mul(point: Point, other) -> Point:
        if isinstance(other, float) or isinstance(other, int):
            x = point.x * other
            y = point.y * other
        else:
            x = point.x * other.x
            y = point.y * other.y
        return Point(x, y)
    
    def __truediv__(self, other) -> Point:
        if isinstance(other, float) or isinstance(other, int):
            x = self.x / other
            y = self.y / other
        else:
            raise NotImplementedError()
        return Point(x, y)
    
    def __floordiv__(self, other) -> Point:
        if isinstance(other, float) or isinstance(other, int):
            x = self.x // other
            y = self.y // other
        else:
            raise NotImplementedError()
        return Point(x, y)
    
    def point_wise_add(self, delta_x, delta_y) -> Point:
        return Point(self.x + delta_x, self.y + delta_y)
    
    def point_dot_product(self, other: Point) -> Point:
        return self * other # Calls __mul

    def as_tuple(self) -> tuple[int, int]:
        return (self.x, self.y)
    
    def as_np_array(self) -> np._ArrayFloat_co:
        np.array([self.x, self.y])

    def rotate(self, degree_angle, clockwise=False) -> Point:
        radians_angle = np.radians(degree_angle)

        change_sign = -1 if clockwise else 1
        rotation_matrix = np.array([
            [np.cos(radians_angle), change_sign*-np.sin(radians_angle)],
            [change_sign*np.sin(radians_angle), np.cos(radians_angle)]
        ]) # Default is counter clock wise rotation

        vector = np.array(self.x, self.y)
        rotated_vector = np.dot(rotation_matrix, vector)

        return Point(float(rotated_vector[0]), float(rotated_vector[1]))
    
    def magnitude(self) -> float:
        return math.sqrt(self.x**2 + self.y**2)
