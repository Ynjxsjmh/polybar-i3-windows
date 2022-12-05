#! /usr/bin/python3

import os
import re
import asyncio
import i3ipc
import pynput
import configparser

from pynput import keyboard
from string import Template


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
COMMAND_PATH = os.path.join(SCRIPT_DIR, 'command.py')
SCROLL_COMMAND_PATH = os.path.join(SCRIPT_DIR, 'scroll.py')


class TitleBar:
    def __init__(self, config_path='config.ini'):
        self.hint = False
        self.hint2win = dict()

        self.config = configparser.ConfigParser()
        self.config.read(os.path.join(SCRIPT_DIR, 'default.ini'))
        self.config.read(os.path.join(SCRIPT_DIR, config_path))

    def get_title_bar(self, i3):
        tree = i3.get_tree()
        # Get current workspace
        focused = tree.find_focused()
        workspace = focused.workspace()

        entries = []
        if len(workspace.nodes) == 1 and workspace.nodes[0].layout == 'tabbed':
            # Ensure first level nodes only contain the tabbed container
            tabbed_con = workspace.nodes[0]
            entries = [ self.format_entry(node) for node in tabbed_con.nodes ]
        else:
            entries = [ self.format_entry(node) for node in workspace.nodes ]

        interval = "%{O"f"{self.config['title']['interval']}""}"
        title_bar = interval.join(entries)

        if not title_bar:
            title_bar = interval

        return title_bar

    def print_title_bar(self, i3, hint=False):
        self.hint = hint
        title_bar = self.get_title_bar(i3)
        print(title_bar, flush=True)

    def format_entry(self, node):
        if len(node.nodes):
            entry = self.format_con(node)
        else:
            entry = self.format_win(node)

        return entry

    def format_con(self, con):
        title = self.make_con_title(con)

        return title

    def format_win(self, app, nested=False):
        '''Format the title of a window

        Parameters
        ----------
        app: i3ipc.con.Con
            A window object
        nested: bool, optional
            If the window is in a container. (default is False)
            If so, the window class is shown to follow i3 behavior.

        Returns
        -------
        str
            A window title formatted with icon, mouse command etc.
        '''

        title   = self.make_title(app, nested=nested)
        command = self.make_command(app)

        title = self.paint_window_icon(app, title)
        title = self.paint_window_num(app, title)

        if self.hint:
            title = self.paint_window_hint(app, title)

        t = Template('%{A1:$left_command:}%{A4:$scroll_up_command:}%{A5:$scroll_down_command:}$title%{A}%{A}%{A}')
        entry = t.substitute(left_command=command['left'],
                             scroll_up_command=command['scroll_up'],
                             scroll_down_command=command['scroll_down'],
                             title=title)

        return entry

    def make_icon(self, app):
        # The icon is defined in the config file by the window class.
        # We need to clear unsupported character in window class
        # because window class should satisfy the key syntax of INI style.
        regex = "[\. ]"
        window_class = app.window_class if app.window_class \
            else app.window_instance if app.window_instance \
            else ''
        window_class = re.sub(regex, '', window_class)
        window_class = window_class.lower()

        icon = self.config['icon'].get(window_class, '')
        font = self.config['general'].getint('icon-font')

        if font:
            return Template('%{T$font}$icon%{T-}').substitute(font=font, icon=icon)
        else:
            return icon

    def make_con_title(self, node):
        if len(node.nodes):
            title = ' '.join(self.make_con_title(n) for n in node.nodes)
            if node.layout == 'splith':
                title = f'H[{title}]'
            elif node.layout == 'splitv':
                title = f'V[{title}]'
            elif node.layout == 'tabbed':
                title = f'T[{title}]'
            elif node.layout == 'stacked':
                title = f'S[{title}]'
            else:
                title = 'not supported'
            return title
        else:
            return self.format_win(node, nested=True)

    def make_title(self, app, nested=False):
        window_class = app.window_class if app.window_class \
            else app.window_instance if app.window_instance \
            else ''
        window_title = app.window_title if app.window_title \
            else app.name if app.name \
            else ''

        title = ''
        title_type = 1 if nested else self.config['title'].getint('title')

        if title_type == 1:
            title = window_class
        else:
            title = window_title

        window_num = len(app.workspace().leaves())
        # consider space between windows
        window_len = self.config['general'].getint('length') // window_num - 1

        # 47 letters equals to 33 
        # we treat 1  as 2 letters for more flexible
        # as we have symbols like H, V, [, ]
        if window_len >= 3:
            if len(title) > window_len:
                title = title[:window_len - 2] + ''
        else:
            title = title[:1] + '•'

        return title

    def make_command(self, app):
        scroll_type = self.config['general']['scroll']

        left_command = '%s %s' % (COMMAND_PATH, app.id)
        scroll_up_command = '%s %s %s' % (SCROLL_COMMAND_PATH, 1, scroll_type)
        scroll_down_command = '%s %s %s' % (SCROLL_COMMAND_PATH, 2, scroll_type)

        command = {
            'left': left_command,
            'scroll_up': scroll_up_command,
            'scroll_down': scroll_down_command,
        }

        return command

    def paint_window_icon(self, app, title):
        icon = self.make_icon(app)

        isIcon    = self.config['title'].getboolean('icon')
        isTitle   = self.config['title'].getint('title') > 0
        underline = self.config['title'].getint('underline')

        ucolor = self.config['color']['focused-window-underline-color'] if app.focused \
            else self.config['color']['urgent-window-underline-color'] if app.urgent  \
            else self.config['color']['window-underline-color']
        ucolor_t = Template('%{+u}%{U$color}$title%{-u}')

        if isIcon and isTitle and underline == 0:
            title = icon + title
        elif isIcon and isTitle and underline == 1:
            title = ucolor_t.substitute(color=ucolor, title=title)
            title = icon + title
        elif isIcon and isTitle and underline == 2:
            icon = ucolor_t.substitute(color=ucolor, title=icon)
            title = icon + title
        elif isIcon and isTitle and underline == 3:
            title = icon + title
            title = ucolor_t.substitute(color=ucolor, title=title)
        elif isIcon and ~isTitle and \
             (underline == 0 or underline == 1):
            title = icon
        elif isIcon and ~isTitle and \
             (underline == 2 or underline == 3):
            title = ucolor_t.substitute(color=ucolor, title=icon)
        elif ~isIcon and isTitle and \
             (underline == 0 or underline == 2):
            title = title
        elif ~isIcon and isTitle and \
             (underline == 1 or underline == 3):
            title = ucolor_t.substitute(color=ucolor, title=title)
        elif ~isIcon and ~isTitle:
            title = icon + title

        fcolor = self.config['color']['focused-window-foreground-color'] if app.focused \
            else self.config['color']['urgent-window-foreground-color'] if app.urgent  \
            else self.config['color']['window-foreground-color']
        title = Template('%{F$color}$title%{F-}').substitute(color=fcolor, title=title)

        bcolor = self.config['color']['focused-window-background-color'] if app.focused \
            else self.config['color']['urgent-window-background-color'] if app.urgent  \
            else self.config['color']['window-background-color']
        title = Template('%{B$color}$title%{B-}').substitute(color=bcolor, title=title)

        return title

    def paint_window_num(self, app, title):
        apps = self.get_leaf_nodes(app.workspace())
        num = apps.index(app) + 1

        isNum = self.config['title'].getint('number')
        isUnderline = self.config['title'].getboolean('underline-number')

        if not isNum:
            return title

        ucolor = self.config['color']['focused-window-number-underline-color'] if app.focused \
            else self.config['color']['urgent-window-number-underline-color'] if app.urgent  \
            else self.config['color']['window-number-underline-color']
        if isUnderline:
            num = Template('%{+u}%{U$color}$num%{-u}').substitute(color=ucolor, num=num)

        fcolor = self.config['color']['focused-window-number-foreground-color'] if app.focused \
            else self.config['color']['urgent-window-number-foreground-color'] if app.urgent  \
            else self.config['color']['window-number-foreground-color']
        num = Template('%{F$color}$num%{F-}').substitute(color=fcolor, num=num)

        bcolor = self.config['color']['focused-window-number-background-color'] if app.focused \
            else self.config['color']['urgent-window-number-background-color'] if app.urgent  \
            else self.config['color']['window-number-background-color']
        num = Template('%{B$color}$num%{B-}').substitute(color=bcolor, num=num)

        return num + title

    def paint_window_hint(self, app, title):
        isNum = self.config['title'].getint('number')

        if isNum:
            return title

        apps = self.get_leaf_nodes(app.workspace())
        num = apps.index(app) + 1

        hints = self.get_hint_strings(len(apps))
        self.hint2win = dict(zip(hints, apps))
        hint = hints[num - 1]

        fcolor = self.config['color']['focused-window-hint-foreground-color'] if app.focused \
            else self.config['color']['urgent-window-hint-foreground-color'] if app.urgent  \
            else self.config['color']['window-hint-foreground-color']
        hint = Template('%{F$color}$hint%{F-}').substitute(color=fcolor, hint=hint)

        bcolor = self.config['color']['focused-window-hint-background-color'] if app.focused \
            else self.config['color']['urgent-window-hint-background-color'] if app.urgent  \
            else self.config['color']['window-hint-background-color']
        hint = Template('%{B$color}$hint%{B-}').substitute(color=bcolor, hint=hint)

        return hint + title

    def get_leaf_nodes(self, node):
        '''Get window objects under a container

        Parameters
        ----------
        node: i3ipc.con.Con
            A container or workspace that contains many sub-containers or windows.

        Returns
        -------
        list
            All windows in the target container.
        '''

        leaves = []

        if len(node.nodes) == 0:
            return [ node ]

        for n in node.nodes:
            leaves += self.get_leaf_nodes(n)

        return leaves

    def get_hint_strings(self, win_count):
        '''
        Returns a list of hint strings which will uniquely identify
        the given number of links. The hint strings may be of different lengths.
        from https://github.com/philc/vimium/blob/master/content_scripts/link_hints.js
        '''
        hint_chars = self.config['title']['hints']
        hints = [""];
        offset = 0

        while (((len(hints) - offset) < win_count) or (len(hints) == 1)):
          hint = hints[offset]
          offset += 1
          for ch in hint_chars:
              hints.append(ch + hint)

        hints = hints[offset:offset+win_count]

        return sorted(hints)


if __name__ == '__main__':

    i3 = i3ipc.Connection()
    title_bar = TitleBar()

    title_bar.print_title_bar(i3)

    BOSS_KEY = {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.KeyCode(char='a')}
    pri_keystroke_set = set()

    with keyboard.Events() as pri_events:
        for pri_event in pri_events:

            if isinstance(pri_event, pynput.keyboard.Events.Press):
                pri_keystroke_set.add(pri_event.key)

            if len(pri_keystroke_set) and isinstance(pri_event, pynput.keyboard.Events.Release):
                '''
                pri_keystroke_set could be empty in two cases:
                1. when entering the event, no key is pressed
                2. pri key has hit the BOSS_KEY, so it is released in inner events
                In both case, we don't need remove keys from it
                '''
                pri_keystroke_set.remove(pri_event.key)

            if pri_keystroke_set == BOSS_KEY:
                # Generate hint
                title_bar.print_title_bar(i3, hint=True)
                hints = title_bar.hint2win.keys()

                # Release boss key
                # Some boss key like ctrl may be hold longer
                with keyboard.Events() as events:
                    for event in events:
                        # 在 release 期间，可能没有释放完全部 boss key，
                        # 而是按其他的键，此时释放的键会出现不在 boss key
                        # 即记录之前按的键（pri_keystroke_set）的中
                        if event.key in pri_keystroke_set and isinstance(event, pynput.keyboard.Events.Release):
                            pri_keystroke_set.remove(event.key)

                        if len(pri_keystroke_set) == 0:
                            break

                # Type hint
                # We need to block them being typed to screen
                is_quit = 0
                sec_keystroke_queue = []
                pynput.keyboard.Listener.suppress = True
                with keyboard.Events() as sec_events:
                    for sec_event in sec_events:
                        if ''.join(sec_keystroke_queue) in hints:
                            break
                        elif sec_event.key == keyboard.Key.esc:
                            is_quit = 1
                            break
                        elif sec_event.key == keyboard.Key.backspace:
                            sec_keystroke_queue = sec_keystroke_queue[:-1]
                        elif isinstance(sec_event.key, pynput.keyboard._xorg.KeyCode):
                            sec_keystroke_queue.append(sec_event.key.char)
                        else:
                            # If sec_event.key is pynput.keyboard._xorg.Key,
                            # ignore those control keys
                            pass

                title_bar.print_title_bar(i3)
                if not is_quit:
                    # Jump to window
                    win = title_bar.hint2win[''.join(sec_keystroke_queue)]
                    win.command('focus')
                pynput.keyboard.Listener.suppress = False
            else:
                title_bar.print_title_bar(i3)
