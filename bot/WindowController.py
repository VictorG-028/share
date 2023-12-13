from enum import Enum
from functools import cached_property
import os
import re
from typing import Literal, Optional
import win32gui, win32ui, win32con
import cv2
import numpy as np
from PIL import Image, ImageGrab
import pyautogui as autogui
from time import sleep

from bot.base.Point import Point

""" Links úteis:
Fast Window Capture
    https://learncodebygaming.com/blog/fast-window-capture
    https://www.youtube.com/watch?v=WymCpVUPWQ4
Documentação da função cDC.BitBlt
    http://www.icodeguru.com/vc&mfc/mfcreference/html/_mfc_cdc.3a3a.bitblt.htm
Print Out Live mouse coordinates
    https://stackoverflow.com/questions/7142342/get-window-position-size-with-python
Get Window/Client coordinates and size
    https://www.programcreek.com/python/example/89832/win32gui.GetClientRect
Bring Window to Front
    https://mail.python.org/pipermail/python-win32/2006-February/004261.html
Template Matching
    ???
"""

class Quadrant(Enum):

    FULL_WINDOW   = 'full-window'
    ONLY_RIHGT    = 'only_right'
    ONLY_LEFT     = 'only_left'
    ONLY_UP       = 'only_up'
    ONLY_BOTTOM   = 'only_bottom'
    TOP_LEFT      = 'top_left'
    TOP_RIGHT     = 'top_right'
    DOWN_LEFT     = 'down_left'
    DOWN_RIGHT    = 'down_right'

    # def __init__(self, w, h):
    #     self.w = w
    #     self.h = h

    # def full_window(self): return (Point(0,0), Point(self.w, self.h))
    # def only_right(self): return (Point(self.w//2, 0), Point(self.w, self.h))
    # def only_left(self): return (Point(0,0), Point(self.w//2, self.h))
    # def only_up(self):   return (Point(0,0), Point(self.w, self.h//2))
    # def only_bottom(self):return (Point(0, self.h//2), Point(self.w, self.h))
    # def top_left(self):   return (Point(0,0), Point(self.w//2, self.h//2))
    # def top_right(self):  return (Point(self.w//2, 0), Point(self.w, self.h//2))
    # def down_left(self): return (Point(0, self.h//2), Point(self.w//2, self.h))
    # def down_right(self):return (Point(self.w//2, self.h//2), Point(self.w, self.h))

    @cached_property
    def ALL_QUADRANT_TYPES():
        return list( Quadrant.__members__.values() )

class WindowController:
    w = 0
    h = 0
    hwnd = None # Window Handle
    top_left: Point = None
    bottom_right: Point = None
    folder_name = None

    def __init__(self, window_name: str, folder_name: str):
        self.folder_name = folder_name
        self.hwnd = win32gui.FindWindow(None, window_name)
        if not self.hwnd:
            raise Exception(f'Window with name {window_name} not found')

        self.update_window_position()
    
    @staticmethod
    def clean_before_exit():
        cv2.destroyAllWindows()


    def update_window_position(self) -> None:
        # window_rect = win32gui.GetWindowRect(self.hwnd)

        _left, _top, _right, _bottom = win32gui.GetClientRect(self.hwnd)
        left, top = win32gui.ClientToScreen(self.hwnd, (_left, _top))
        right, bottom = win32gui.ClientToScreen(self.hwnd, (_right, _bottom))

        self.w = right - left
        self.h = bottom - top

        self.top_left = Point(left, top)
        self.bottom_right = Point(right, bottom)


    def fast_screenshot(self, 
                        top_left: Point = Point(0,0), 
                        bottom_right: Point = None, 
                        trim: bool = False
                        ) -> np.ndarray:
        
        # Avoid NameError: name 'self' is not defined by making bottom_right default value equal Point(self.w, self.h)
        bottom_right = bottom_right or Point(self.w, self.h)

        # Get width and height of a rectangle inside the window
        w, h = bottom_right.x - top_left.x, bottom_right.y - top_left.y

        # get the window image data
        wDC = win32gui.GetWindowDC(self.hwnd)
        dcObj = win32ui.CreateDCFromHandle(wDC)
        cDC = dcObj.CreateCompatibleDC()
        dataBitMap = win32ui.CreateBitmap()
        dataBitMap.CreateCompatibleBitmap(dcObj, self.w, self.h)
        cDC.SelectObject(dataBitMap)
        cDC.BitBlt(top_left.as_tuple(), (w, h), dcObj, top_left.as_tuple(), win32con.SRCCOPY)

        # convert the raw data into a format opencv can read
        #dataBitMap.SaveBitmapFile(cDC, 'debug.bmp')
        signedIntsArray = dataBitMap.GetBitmapBits(True)
        img = np.fromstring(signedIntsArray, dtype='uint8')
        img.shape = (self.h, self.w, 4)

        # free resources
        dcObj.DeleteDC()
        cDC.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, wDC)
        win32gui.DeleteObject(dataBitMap.GetHandle())

        # drop the alpha channel, or cv.matchTemplate() will throw an error like:
        #   error: (-215:Assertion failed) (depth == CV_8U || depth == CV_32F) && type == _templ.type() 
        #   && _img.dims() <= 2 in function 'cv::matchTemplate'
        img = img[...,:3]

        # make image C_CONTIGUOUS to avoid errors that look like:
        #   File ... in draw_rectangles
        #   TypeError: an integer is required (got type tuple)
        # see the discussion here:
        # https://github.com/opencv/opencv/issues/14866#issuecomment-580207109
        img = np.ascontiguousarray(img)

        # Remove black space around the rectangle screenshot
        if trim:
           img = img[top_left.y:bottom_right.y , top_left.x:bottom_right.x] 

        return img
    

    def slow_screenshot(self, 
                        top_left: Optional[Point] = None, 
                        bottom_right: Optional[Point] = None,
                        should_save: bool = False,
                        save_path: str = ".",
                        filename: str = "default_name",
                        filetype: str = "png",
                        game: Literal["wakfu"] = "wakfu"
                        ) -> None | Image.Image:
        
        self.maximize()
        self.to_front(click_on_window_to_force_focus = True)
        sleep(1)
        
        top_left = top_left or self.top_left
        bottom_right = bottom_right or self.bottom_right

        bbox = (*top_left, *bottom_right)
        screenshot = ImageGrab.grab(bbox)
        
        special_case = game
        if special_case == "Wakfu":

            def find_next_id():
                folder_path = 'C:/Users/eduar/OneDrive/Área de Trabalho/Window Automation Framework/Images/Wakfu/capt_nyacha'

                files = os.listdir(folder_path)
                png_files = [file for file in files if file.lower().endswith('.png')]
                pattern = re.compile(r'capt_cat_(\d+)\.png')
                existing_numbers = [int(pattern.search(file).group(1)) for file in png_files]
                max_number = max(existing_numbers, default=0)

                return max_number + 1
            i = find_next_id()
            save_path = "C:/Users/eduar/OneDrive/Área de Trabalho/Window Automation Framework/Images/Wakfu/capt_nyacha"
            filename = f"capt_cat_{i}"
            filetype = "png"

            if should_save:
                screenshot.save(f"{save_path}/{filename}.{filetype}")
            return None

        if should_save:
            # TODO ver um geito de considerar um folder dentro de images
            # TODO modificar save_path não deve quebrar essa linha
            screenshot.save(f"{save_path}/Images/{game}/{filename}.{filetype}")
            return None
        
        return screenshot


    def save_screenshot(self,
                        name: str, 
                        arr: Optional[np.ndarray] = None, 
                        img: Optional[Image.Image] = None, 
                        file_type = "png",
                        save_path = "./",
                        ) -> None:

        if img == None:
            img = Image.fromarray(arr)
        img.save(f"{save_path}/{name}.{file_type}")


    #  TODO Add type QuadrantValue to this file
    def show_screenshot_continuously(self, scan_quadrant = 'full-window') -> None:
        scan_quadrants = {
            'full-window': (Point(0,0), Point(self.w, self.h)),
            'only-right':  (Point(self.w//2, 0), Point(self.w, self.h)),
            'only-left':   (Point(0,0), Point(self.w//2, self.h)),
            'only-up':     (Point(0,0), Point(self.w, self.h//2)),
            'only-bottom': (Point(0, self.h//2), Point(self.w, self.h)),
            'up-left':     (Point(0,0), Point(self.w//2, self.h//2)),
            'up-right':    (Point(self.w//2, 0), Point(self.w, self.h//2)),
            'down-left':   (Point(0, self.h//2), Point(self.w//2, self.h)),
            'down-right':  (Point(self.w//2, self.h//2), Point(self.w, self.h)),
        }
        search_rect = scan_quadrants.get(scan_quadrant)
        while True:
            screenshot = self.fast_screenshot(*search_rect)
            cv2.imshow("Screenshot", screenshot)

            if cv2.waitKey(1) == ord('q'):
                break


    def maximize(self) -> None:
        # win32gui.ShowWindow(self.hwnd, win32con.SW_MAXIMIZE)
        win32gui.ShowWindow(self.hwnd, win32con.SW_NORMAL)


    def to_front(self, click_on_window_to_force_focus = False) -> None:
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.BringWindowToTop(self.hwnd)

        if click_on_window_to_force_focus:
            self.move_to(Point(10, 10), {'width': 0, 'height': 0})
            WindowController.click()

        sleep(1)

    
    def is_maximized(self) -> bool:
        """ Retrun True if window is maximized"""
        # http://timgolden.me.uk/pywin32-docs/win32gui__GetWindowPlacement_meth.html
        _1, state, _3, _4, _5, = win32gui.GetWindowPlacement(self.hwnd)
        # return state == win32con.SW_SHOWMAXIMIZED
        return state == win32con.SW_SHOWNORMAL


    QuadrantValue = Literal['full-window', 'only-right', 'only-left', 'only-top', 'only-bottom', 'top-left', 'top-right', 'down-left', 'down-right']
    def find_button(self, 
                    button_img_name: str, 
                    scan_quadrant: QuadrantValue = 'full-window'
                    ) -> tuple[Point, dict[str, int]]:
        """
        scan_quadrant values are:
            'full-window' 'only-right' 'only-left'
            'only-top' 'only-bottom' 'top-left'
            'top-right' 'down-left' 'down-right'
        """
        scan_quadrants = {
            'full-window': (Point(0,0), None), # Point(self.w, self.h)
            'only-right':  (Point(self.w//2, 0), Point(self.w, self.h)),
            'only-left':   (Point(0,0), Point(self.w//2, self.h)),
            'only-top':     (Point(0,0), Point(self.w, self.h//2)),
            'only-bottom': (Point(0, self.h//2), Point(self.w, self.h)),
            'top-left':     (Point(0,0), Point(self.w//2, self.h//2)),
            'top-right':    (Point(self.w//2, 0), Point(self.w, self.h//2)),
            'down-left':   (Point(0, self.h//2), Point(self.w//2, self.h)),
            'down-right':  (Point(self.w//2, self.h//2), Point(self.w, self.h)),
        }
        search_rect = scan_quadrants.get(scan_quadrant)

        img = self.fast_screenshot(*search_rect)
        # TODO: make a debug option to see image
        # cv2.imshow('Uncomment to see take_screenshot return',img)
        # cv2.waitKey(0)
        template = cv2.imread(f"images/{self.folder_name}/{button_img_name}.png")

        # All the 6 methods for comparison in a list
        methods = ['cv2.TM_CCOEFF', 'cv2.TM_CCOEFF_NORMED', 'cv2.TM_CCORR', 'cv2.TM_CCORR_NORMED', 'cv2.TM_SQDIFF', 'cv2.TM_SQDIFF_NORMED']
 
        res = cv2.matchTemplate(img, template, eval(methods[1]))
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        # print(f"{min_val}, {max_val}, {min_loc}, {max_loc}")

        return Point(*max_loc), {'width': template.shape[1], 'height': template.shape[0]}


    def move_to(self, 
                screen_point: Point, 
                rectangle_shape: None | dict[str, int], 
                duration: float = 0.2
                ) -> None:
        # print(screen_point)
        # print(type(screen_point))
        # print(self.top_left)
        # print(type(self.top_left))
        relative_to_sreen_coordinate = self.top_left + screen_point
        destination_point = relative_to_sreen_coordinate
        if rectangle_shape is not None:
            certer_button_point = (
                relative_to_sreen_coordinate.x + rectangle_shape['width']//2,
                relative_to_sreen_coordinate.y + rectangle_shape['height']//2,
            )
            destination_point = certer_button_point

        autogui.moveTo(*destination_point)
        sleep(duration)

    
    # displace near
    def move_relative(self, 
                      delta_x, 
                      delta_y, 
                      duration: float = 0.2
                      ) -> None:

        autogui.moveRel(delta_x, delta_y)
        sleep(duration)

    
    @staticmethod
    def click(
            mouse = True, 
            mouse_button: Literal['left', 'right'] = 'left', 
            keyboard_button = 'space', 
            hold = 0.2, 
            pos_action_delay = 0.2,
            double_click = False
        ) -> None:
        
        if mouse:
            for number_of_clicks in range(0, 1 + 1*double_click):
                # autogui.click(button='left', duration=1.0)
                autogui.mouseDown(button=mouse_button)
                sleep(hold)
                autogui.mouseUp(button=mouse_button)
            sleep(pos_action_delay)
        else: 
            raise Exception("Click with keyboard not implemented")
        
    @staticmethod
    def scroll(down = False):
        """
        Send the mouse vertical scroll event to Windows by calling the mouse_event() win32 function.
        up = foward = positive int value
        down = backward = negative int value
        """

        # TODO: descobri pq o comando scroll não funciona no wakfu
        value = 10

        if down:
            value *= -1

        autogui.scroll(value)
        
    @property
    def resolution(self) -> str:
        resolution = self.bottom_right - self.top_left
        return f"{resolution.x} X {resolution.y}"

    @property
    def center(self) -> Point:
        length, height = self.bottom_right - self.top_left
        return Point(length / 2, height / 2)
