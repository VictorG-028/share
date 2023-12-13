from __future__ import annotations

from bot.base.Point import Point

class Rect:
    top_left: Point
    bottom_right: Point
    
    def __init__(self, top_left: int, bottom_right: int) -> None:
        assert type(top_left) == type(bottom_right) == Point
        self.top_left = top_left
        self.bottom_right = bottom_right

    def __str__(self) -> str:
        return f"({self.top_left}, {self.bottom_right})"

    # Allow iterate over atribute values (in this case, x and y)
    def __iter__(self) -> int:
        for value in self.__dict__.values():
            yield value

    @property
    def top(self) -> int: return self.top_left.y
    @property
    def right(self) -> int: return self.bottom_right.x
    @property
    def bottom(self) -> int: return self.bottom_right.y
    @property
    def left(self) -> int: return self.top_left.x
