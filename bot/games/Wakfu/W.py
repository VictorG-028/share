from typing import Literal, Optional
from enum import Enum
from functools import cached_property, lru_cache
import random
from time import sleep
import numpy as np
from PIL import Image, ImageDraw
import pyautogui
from bot.WindowController import WindowController
from bot.base.Point import Point


window = WindowController("WAKFU", "Wakfu")

class ItemType(Enum):
    NIL = None
    SEED = "seed" # Herborista e Fazendéiro
    TREE = "tree" # Lenhador

    @cached_property
    def ALL_ITEM_TYPES():
        return list( ItemType.__members__.values() )

class Direction:

    """ Vetores constantes para calcular coordenadas no tabuleiro de wakfu
    
    ### I Considerar um tabuleiro girado em 45 graus com grid de quadrados de lado l
            columns
    row    '/ '/ '/ '
         ------------
    row  '/ '/ '/ '
       -----------   _
    row '/ '/ '/ '  / l = lado do quadrado = distância de coordenada do mouse
               -
       |--|
        l = distância da coordenada do mouse 
     |--|
       l = lado do quadrado

       (1) delta_x² + delta_y² = l²
       (2) cos(45) = delta_x / l
       (3) sen(45) = delta_y / l
       (junta 2 e 3) delta_x == delta_y == cos(45) * l

    ### II Considerar um tabuleiro como um espaço vetorial formado pela rotação de 45º graus e quadrados de lado l

    # TODO - ver como fazer assim

    """
    #TODO: achar a coordenada do quadrado que o personmagem está em cima sem usar largura,altura da janela

    __SQUARE_LENGTH__ = 65             # Pixel length (approximation) of a wakfu grid 45º-rotated square
    __COS_45__ = np.cos(np.pi/4)       # sen(45º) == cos(45º) == np.cos(np.pi/4) == np.sqrt(2)/2
    __SEN_45__ = np.sin(np.pi/4)       # sen(45º) == cos(45º) == np.cos(np.pi/4) == np.sqrt(2)/2

    # @cached_property
    # DELTA_X = lambda self: self.SQUARE_LENGTH*self.COS_45 # delta_x == delta_y == l * sen(45º) == l * cos(45º) 
    __DELTA_X__ = __SQUARE_LENGTH__*__SEN_45__ # delta_x == delta_y == l * sen(45º) == l * cos(45º) 
    __DELTA_Y__ = __SQUARE_LENGTH__*__COS_45__ # delta_x == delta_y == l * sen(45º) == l * cos(45º) 

    NORTH_VECTOR = Point( __DELTA_X__,  __DELTA_Y__)
    SOUTH_VECTOR = -NORTH_VECTOR
    EAST_VECTOR  = Point( __DELTA_X__, -__DELTA_Y__)
    WEST_VECTOR  = -EAST_VECTOR

    # @cached_property
    @staticmethod
    def CENTER(): return (Point(*window.center) + Point(5, 2))
    @staticmethod
    @lru_cache()
    def NORTH(n=1): return Direction.CENTER() + n * Point(Direction.__DELTA_X__, -Direction.__DELTA_Y__)
    @staticmethod
    @lru_cache()
    def SOUTH(n=1): return Direction.CENTER() + n * Point(-Direction.__DELTA_X__, Direction.__DELTA_Y__)
    @staticmethod
    @lru_cache()
    def EAST(n=1): return Direction.CENTER() + n * Point(Direction.__DELTA_X__, Direction.__DELTA_Y__)
    @staticmethod
    @lru_cache()
    def WEST(n=1): return Direction.CENTER() + n * Point(-Direction.__DELTA_X__, -Direction.__DELTA_Y__)

    @staticmethod
    @lru_cache()
    def GET_SQUARE_COORD(x: int, y: int):
        return x * Direction.NORTH + y * Direction.EAST

    # @cached_property
    @staticmethod
    def HARDCODE_CENTER(): return (Point(*window.center) + Point(5, 2))
    @staticmethod
    @lru_cache()
    def HARDCODE_NORTH(n=1): return n * Point(57.125, -29.375)
    @staticmethod
    @lru_cache()
    def HARDCODE_SOUTH(n=1): return n * Point(-57.125, 29.375)
    @staticmethod
    @lru_cache()
    def HARDCODE_EAST(n=1): return n * Point(58.75, 29.75)
    @staticmethod
    @lru_cache()
    def HARDCODE_WEST(n=1): return n * Point(-58.75, -29.75)

    @staticmethod
    @lru_cache()
    def HARDCODE_SPAM_COORD(x: int = 1, y: int = 0):
        return Direction.HARDCODE_CENTER() + \
            Direction.HARDCODE_NORTH(x) + Direction.HARDCODE_EAST(y)


class WUI:
    UP = Point(0, -40)



def login() -> None:
    window.to_front(click_on_window_to_force_focus = True)
    sleep(2)

    # coords = [ Point(685,805), Point(468,456), Point(291,324) ]
    # coords = [ window.top_left+p for p in coords]
    # delays = [ 6, 6, 6 ]
    # double_clicks = [ False, True, True ]

    # for p, d, double_click in zip(coords, delays, double_clicks):
    #     window.move_to(p, None)
    #     window.click(double_click=double_click)
    #     sleep(d)


    point, shape = window.find_button("steam_login_button", scan_quadrant='only-bottom')
    window.move_to(point, shape)
    # print(point, shape)
    window.click(pos_action_delay=10.0)

    point, shape = window.find_button("INT_server_button")
    window.move_to(point, shape)
    # print(point, shape)
    window.click(hold=0.1, pos_action_delay=6.0, double_click=True)

    point, shape = window.find_button("OSA_char_selector", scan_quadrant='only-top')
    window.move_to(point, shape)
    # print(point, shape)
    window.click(hold=0.1, pos_action_delay=6.0, double_click=True)

    print("Login executado")



def put_item(
        m: int, n: int, # size: tuple[int, int], 
        item_type: Optional[ItemType] = None, 
        start_direction: Direction = Direction.NORTH
    ) -> None:
    
    window.to_front(click_on_window_to_force_focus = True)
    sleep(2)

    start_point = Direction.CENTER
    current_point = start_direction


    # arrastar o mouse dessa coordenada até o fin da coluna
    for column in range(m):
        for row in range(n):
            window.move_to(current_point)
            window.click(pos_action_delay=6) # plant
            # window.click(pos_action_delay=2) # walk to tile
            if row == 0 and column % 2 == 0:
                current_point = Direction.NORTH(2)
            elif row == 0 and column != 2:
                current_point = Direction.SOUTH



        current_point = Direction.NORTH(1)
        window.move_to(current_point)
        window.click(pos_action_delay=2)

        current_point = Direction.EAST(1)
        window.move_to(current_point)
        window.click(pos_action_delay=6)
        
        window.click(pos_action_delay=2)
        current_point = Direction.SOUTH(1)

    # passar para o proxima linha coluna
    # repetir ate acabar

    # TODO think about a method to swipe a mouse over a row/column
    ## The lenght of the swipe is a function of m or n
    ## The swipe can make a curve and need to be very fast, otherwise, there will be a swipe per row or column


def farm_troll_minigame(runs = 1) -> None:

    window.to_front(click_on_window_to_force_focus = True)
    sleep(1)

    point_SDV, shape_SDV = window.find_button("SDV_icon")

    # 16 squares run
    coords = [
        (2,0), (2,0), (0,-1), (0,1), 
        (0,-2), (0, -3), (1,0), (-1,0), 
        (-2,0), (0,-1), (0,1), 
        (-2,0), (0,-1), (0,1), 
        (-2,-1), (0,-1), 
        # (-2,0), (0,-1), 
        # (0,-4), (1,0), 
        # (0,-2), (1,0), (-1,0)
    ]
    # 17 squares run
    coords = [
        (3,0), (0,-1), (0,1), 
        (0,-4), (1,0), (-1,0), 
        (-2,0), (0,-1), (0,1), 
        (-2,0), (0,-1), (0,1), 
        (-2,-1), (0,-1), 
        (-2,0), (0,-1), (1,0), 
        # (0,-4), (1,0), 
        # (0,-2), (1,0), (-1,0)
    ]
    npc_coord = (2,-6) # (1,-5)

    # Enter the game
    point, shape = window.find_button("gravedigger_npc")
    window.move_to(point, shape)
    window.click(mouse_button='right')
    window.move_relative(0, -40)
    window.click(pos_action_delay=4)
    
    for _ in range(runs):
        print(_)
        
        if (_ != 0):
            # Reenter the game
            window.move_to(Direction.HARDCODE_SPAM_COORD(*npc_coord), None)
            window.click(mouse_button='right')
            window.move_relative(0, -40)
            window.click(pos_action_delay=4)

        # Open the game door (start game)
        window.move_to(Direction.HARDCODE_SPAM_COORD(1,0) + Point(-10, 10), None)
        window.click(mouse_button='right')
        window.move_relative(0, -40)
        window.click()

        # Start digging
        for coord in coords:
            window.move_to(Direction.HARDCODE_SPAM_COORD(*coord), None)
            window.click(mouse_button='right')
            window.move_relative(0, -40)
            window.click(mouse_button='right', pos_action_delay=1.85)

        sleep(random.uniform(3.0, 6.0)) # Wait exit the game

        choice = random.uniform(1, 20)
        if choice < 5:
            # walk around
            window.move_to(Direction.HARDCODE_SPAM_COORD(-3,-1), None)
            window.click(mouse_button='right')
            window.click(mouse_button='left', pos_action_delay=1.7, hold=0)

            window.move_to(Direction.HARDCODE_SPAM_COORD(-2,-1), None)
            window.click(mouse_button='left', pos_action_delay=1.7, hold=0)

            window.move_to(Direction.HARDCODE_SPAM_COORD(0,1), None)
            window.click(mouse_button='left', pos_action_delay=1.7, hold=0)

            window.move_to(Direction.HARDCODE_SPAM_COORD(0,-1), None)
            window.click(mouse_button='left', pos_action_delay=1.7, hold=0)

            window.move_to(Direction.HARDCODE_SPAM_COORD(5,2), None)
            window.click(mouse_button='left', pos_action_delay=4.5, hold=0)

            if choice == 4: # Open and exit SDV
                window.move_to(point_SDV, shape_SDV)
                window.click(mouse_button='left')
                sleep(7)
                # window.move_to(point_SDV, shape_SDV)
                window.click(mouse_button='left')
                sleep(7)


def farm_water(
        direction: Literal['north', 'east', 'south', 'west'],
        ammout: int = 1000
    ) -> None:

    window.to_front(click_on_window_to_force_focus = True)
    sleep(2)

    input_to_gridCoord = {
        'north': (1, 0),
        'east': (0, 1),
        'south': (-1, 0),
        'west': (0, -1),
    }

    screen_point = Direction.HARDCODE_SPAM_COORD(*input_to_gridCoord[direction])

    window.move_to(screen_point, None)
    window.click(mouse_button='right')

    point, shape = window.find_button("collect_button")
    # window.move_relative(*WUI.up)
    window.move_to(point, shape)
    window.click(pos_action_delay=3.5)

    for _ in range(ammout):
        window.move_to(screen_point, None)
        window.click(mouse_button='right')

        window.move_to(point, shape)
        window.click(pos_action_delay=3.5)


def farm_coal(iterations = 3, local = 'astrub') -> None:
    
    window.to_front(click_on_window_to_force_focus = True)
    sleep(2)

    coords = [
        (0,-1), (-2,-1), (-5,-2), (-1,0), 
        (-4,-1), (-2,-3), 
        (2,-4), (9,-2), (2, -3), (0,-7),
        (0,-6), (-4,-2), (0,-3), (1,-6), (0,6), (6,4),
        (3,-4), (0,0)

        # Walk back to start
    ]

    actions = [
        'collect', 'collect', 'collect', 'walk', 
        'collect', 'walk', 
        'collect', 'collect', 'collect', 'walk',
        'collect', 'collect', 'collect', 'collect', 'walk', 'walk',
        'collect', 'walk'
    ]

    for i in range(iterations):
        point, shape = window.find_button("first_coal")
        window.move_to(point, shape)
        window.click(mouse_button='right')
        window.move_relative(0, -40)
        window.click(pos_action_delay=6.0)

        for coord, action in zip(coords, actions):
            window.move_to(Direction.HARDCODE_SPAM_COORD(*coord), None)
            if action == 'collect':
                window.click(mouse_button='right')
                window.move_relative(0, -40)
                window.click(mouse_button='right', pos_action_delay=4.5)
            elif action == 'walk':
                window.click(mouse_button='left', pos_action_delay=3.0)


def farm_quaqua_minigame(runs = 400) -> None:
    
    window.to_front(click_on_window_to_force_focus = True)
    sleep(1)

    coords = [
        (0,0), (0,0), (0,0), 
        (0,0)
    ]

    

def square_walk(square_tiles = 3) -> None:

    window.to_front(click_on_window_to_force_focus = True)

    window.move_to(Direction.NORTH(square_tiles), None)

    create_transparent_image_with_dots(Direction.CENTER(), Direction().NORTH(square_tiles))
    # window.click(pos_action_delay=0.3*3)
    
    # window.move_to(Direction().WEST(square_tiles), None)
    # window.click(pos_action_delay=0.3*3)

    # window.move_to(Direction().SOUTH(square_tiles), None)
    # window.click(pos_action_delay=0.3*3)

    # window.move_to(Direction().EAST(square_tiles), None)
    # window.click(pos_action_delay=0.3*3)


def create_transparent_image_with_dots(p1: Point, p2: Point, dot_radius=5, output_path='output.png'):
    # Get the screen size
    # screen_width, screen_height = pyautogui.size
    pair = window.resolution.split(" X ")
    screen_width = int(pair[0])
    screen_height = int(pair[1])

    # Create a transparent image with screen size
    img = Image.new('RGBA', (screen_width, screen_height), (0, 0, 0, 0))

    # Create a draw object
    draw = ImageDraw.Draw(img)

    # Plot dots on the image
    draw.ellipse((p1.x - dot_radius, p1.y - dot_radius, p1.x + dot_radius, p1.y + dot_radius), fill='red')
    draw.ellipse((p2.x - dot_radius, p2.y - dot_radius, p2.x + dot_radius, p2.y + dot_radius), fill='blue')

    # Save the image
    img.save(output_path)


# UTIL wakfu functions #########################################################

def look_at(direction: Direction):

    direction_mapping = {
        Direction.NORTH: 'up',
        Direction.SOUTH: 'down',
        Direction.EAST: 'right',
        Direction.WEST: 'left'
    }

    if direction in direction_mapping:
        pyautogui.press(direction_mapping[direction])
    else:
        raise ValueError("Pass a valid direction. Can only look at [NOTH, SOUTH, EAST, WEST].")
