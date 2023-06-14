#! /usr/bin/python3

import os
import re
import json
import asyncio
import i3ipc
import pynput
import tkinter
import configparser

from loguru import logger
from pynput import keyboard
from string import Template
from threading import Thread


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
COMMAND_PATH = os.path.join(SCRIPT_DIR, 'command.py')
SCROLL_COMMAND_PATH = os.path.join(SCRIPT_DIR, 'scroll.py')


class TitleBar:
    def __init__(self, config_path='config.ini'):
        self.hint = False
        self.hint2win = dict()
        self.win2hint = dict()
        self.hint_trie = None

        self.config = configparser.ConfigParser()
        self.config.read(os.path.join(SCRIPT_DIR, 'default.ini'))
        self.config.read(os.path.join(SCRIPT_DIR, config_path))

        self.tk = tkinter.Tk()
        self.keystroke_queue = []

        self.i3 = i3ipc.Connection()
        self.i3.on('window', self._refresh_title_bar)
        self.i3.on('window::focus', self._refresh_title_bar)
        self.i3.on('workspace::focus', self._refresh_title_bar)

    def launch_i3(self):
        t_i3 = Thread(target=self.i3.main)
        t_i3.start()

    def _refresh_title_bar(self, i3conn, event):
        self.print_title_bar()

    def get_title_bar(self):
        tree = self.i3.get_tree()
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

    def print_title_bar(self, hint=False):
        self.hint = hint
        title_bar = self.get_title_bar()
        print(title_bar, flush=True)

    def format_entry(self, node):
        if len(node.nodes):
            # A container could contains many windows.
            # If a node has a list of nodes,
            # then it is a container.
            entry = self.format_con(node)
        else:
            entry = self.format_win(node)

        return entry

    def format_con(self, con):
        title = self.make_con_title(con)

        return title

    def format_win(self, win, nested=False):
        '''Format the title of a window

        Parameters
        ----------
        win: i3ipc.con.Con
            A window object
        nested: bool, optional
            If the window is in a container. (default is False)
            If so, the window class is shown to follow i3 behavior.

        Returns
        -------
        str
            A window title formatted with icon, mouse command etc.
        '''

        title   = self.make_title(win, nested=nested)
        command = self.make_command(win)

        title = self.paint_window_icon(win, title)
        title = self.paint_window_num(win, title)

        if self.hint:
            title = self.paint_window_hint(win, title)

        t = Template('%{A1:$left_command:}%{A4:$scroll_up_command:}%{A5:$scroll_down_command:}$title%{A}%{A}%{A}')
        entry = t.substitute(left_command=command['left'],
                             scroll_up_command=command['scroll_up'],
                             scroll_down_command=command['scroll_down'],
                             title=title)

        return entry

    def make_icon(self, win):
        # The icon is defined in the config file by the window class.
        # We need to clear unsupported character in window class
        # because window class should satisfy the key syntax of INI style.
        regex = "[\. ]"
        window_class = win.window_class if win.window_class \
            else win.window_instance if win.window_instance \
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

    def make_title(self, win, nested=False):
        window_class = win.window_class if win.window_class \
            else win.window_instance if win.window_instance \
            else ''
        window_title = win.window_title if win.window_title \
            else win.name if win.name \
            else ''

        title = ''
        title_type = 1 if nested else self.config['title'].getint('title')

        if title_type == 1:
            title = window_class
        else:
            title = window_title

        window_num = len(win.workspace().leaves())
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

    def make_command(self, win):
        scroll_type = self.config['general']['scroll']

        left_command = '%s %s' % (COMMAND_PATH, win.id)
        scroll_up_command = '%s %s %s' % (SCROLL_COMMAND_PATH, 1, scroll_type)
        scroll_down_command = '%s %s %s' % (SCROLL_COMMAND_PATH, 2, scroll_type)

        command = {
            'left': left_command,
            'scroll_up': scroll_up_command,
            'scroll_down': scroll_down_command,
        }

        return command

    def paint_window_icon(self, win, title):
        icon = self.make_icon(win)

        isIcon    = self.config['title'].getboolean('icon')
        isTitle   = self.config['title'].getint('title') > 0
        underline = self.config['title'].getint('underline')

        ucolor = self.config['color']['focused-window-underline-color'] if win.focused \
            else self.config['color']['urgent-window-underline-color'] if win.urgent  \
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

        fcolor = self.config['color']['focused-window-foreground-color'] if win.focused \
            else self.config['color']['urgent-window-foreground-color'] if win.urgent  \
            else self.config['color']['window-foreground-color']
        title = Template('%{F$color}$title%{F-}').substitute(color=fcolor, title=title)

        bcolor = self.config['color']['focused-window-background-color'] if win.focused \
            else self.config['color']['urgent-window-background-color'] if win.urgent  \
            else self.config['color']['window-background-color']
        title = Template('%{B$color}$title%{B-}').substitute(color=bcolor, title=title)

        return title

    def paint_window_num(self, win, title):
        wins = self.get_leaf_nodes(win.workspace())
        num = wins.index(win) + 1

        isNum = self.config['title'].getint('number')
        isUnderline = self.config['title'].getboolean('underline-number')

        if not isNum:
            return title

        ucolor = self.config['color']['focused-window-number-underline-color'] if win.focused \
            else self.config['color']['urgent-window-number-underline-color'] if win.urgent  \
            else self.config['color']['window-number-underline-color']
        if isUnderline:
            num = Template('%{+u}%{U$color}$num%{-u}').substitute(color=ucolor, num=num)

        fcolor = self.config['color']['focused-window-number-foreground-color'] if win.focused \
            else self.config['color']['urgent-window-number-foreground-color'] if win.urgent  \
            else self.config['color']['window-number-foreground-color']
        num = Template('%{F$color}$num%{F-}').substitute(color=fcolor, num=num)

        bcolor = self.config['color']['focused-window-number-background-color'] if win.focused \
            else self.config['color']['urgent-window-number-background-color'] if win.urgent  \
            else self.config['color']['window-number-background-color']
        num = Template('%{B$color}$num%{B-}').substitute(color=bcolor, num=num)

        return num + title

    def paint_window_hint(self, win, title):
        isNum = self.config['title'].getint('number')

        if isNum:
            return title

        wins = []
        for workspace in self.get_visible_workspaces():
            wins += self.get_leaf_nodes(workspace)
        win_ids = [win.id for win in wins]
        num = win_ids.index(win.id) + 1

        hints = self.get_hint_strings(len(wins))
        self.hint2win = dict(zip(hints, win_ids))
        self.win2hint = dict(zip(win_ids, hints))
        self.hint_trie = self.get_hint_trie(hints)
        hint = hints[num - 1]

        fcolor = self.config['color']['focused-window-hint-foreground-color'] if win.focused \
            else self.config['color']['urgent-window-hint-foreground-color'] if win.urgent  \
            else self.config['color']['window-hint-foreground-color']
        hint = Template('%{F$color}$hint%{F-}').substitute(color=fcolor, hint=hint)

        bcolor = self.config['color']['focused-window-hint-background-color'] if win.focused \
            else self.config['color']['urgent-window-hint-background-color'] if win.urgent  \
            else self.config['color']['window-hint-background-color']
        hint = Template('%{B$color}$hint%{B-}').substitute(color=bcolor, hint=hint)

        return hint + title

    def paint_window_hint_on_screen(self):
        '''Show hints for visible windows above it.
        When there is only one visible window, it won't
        show hint above it.
        When the visible window is also the focused window,
        it won't have above window hint.
        '''

        if tkinter._default_root is None:
            self.tk = tkinter.Tk()
        # Disable the tkinter title bar
        # wm_overrideredirect would prevent keyboard listening
        self.tk.wm_attributes('-type', 'splash')
        self.tk.geometry("{0}x{1}+0+0".format(self.tk.winfo_screenwidth(), self.tk.winfo_screenheight()))

        self.tk.configure(bg='')

        wins = []
        for workspace in self.get_visible_workspaces():
            wins += workspace.leaves()
        visible_wins = [win for win in wins if self.get_container_visibility(win)]
        focused_win = self.i3.get_tree().find_focused()

        if len(visible_wins) > 1:
            for win in visible_wins:
                if win.id == focused_win.id:
                    continue
                hint = self.win2hint[win.id]
                label = tkinter.Label(text=hint, font=("", 60))
                x = win.rect.x + win.rect.width/2 - label.winfo_reqwidth()/2
                y = win.rect.y + win.rect.height/2 - label.winfo_reqheight()/2
                label.place(x=x, y=y)

        self.tk.bind("<Key>", self.check_hint_key)

        self.tk.mainloop()

    def paint_workspace_hint_on_screen(self):
        '''Show windows under all workspaces with hint on screen
        '''
        if tkinter._default_root is None:
            self.tk = tkinter.Tk()
        # Disable the tkinter title bar
        # wm_overrideredirect would prevent keyboard listening
        self.tk.wm_attributes('-type', 'splash')

        self.tk.configure(bg='')

        workspaces = [workspace for workspace in self.i3.get_tree().workspaces()
                      if len(workspace.nodes)]
        # Leaves are not always application windows
        wins = []
        for workspace in workspaces:
            wins.append(workspace.leaves())
        win_ids = [win.id for ws in wins for win in ws]

        hints = self.get_hint_strings(len(win_ids))
        self.hint2win = dict(zip(hints, win_ids))
        self.win2hint = dict(zip(win_ids, hints))
        self.hint_trie = self.get_hint_trie(hints)

        ncol = len(workspaces)
        tot_width = 100
        col_width = tot_width // ncol

        # The head row
        for j in range(ncol):
            t = tkinter.Entry(self.tk, width=col_width,
                              font=('', 16, 'bold'),
                              exportselection=False,
                              justify='center')
            t.insert('end', workspaces[j].name)
            t.config(state='disabled')
            if workspaces[j].focused:
                t.config(disabledforeground='blue')
            t.grid(row=0, column=j)

        def on_release(event):
            text = event.widget
            hint = text.get(*text.tag_ranges('hint'))
            win_id = self.hint2win[hint]
            self.keystroke_queue = []
            self.tk.destroy()
            win = self.i3.get_tree().find_by_id(win_id)
            win.command('focus')

        # The window content
        for j in range(ncol):
            for i in range(len(wins[j])):
                win = wins[j][i]
                hint = self.win2hint[win.id]
                win_text = tkinter.Text(self.tk, width=col_width, height=1,
                                        font=('', 16),
                                        exportselection=False,
                                        borderwidth=1, relief='solid')
                win_text.insert('end', hint+win.name)
                win_text.bind('<ButtonRelease-1>', on_release)
                win_text.grid(row=i+1, column=j)
                # Disable text selection in another way:
                # by setting the selection bg to default
                win_text.config(state='disabled',
                                selectbackground=win_text.cget('bg'),
                                inactiveselectbackground=win_text.cget('bg'))
                win_text.tag_add('hint', '1.0', f'1.{len(hint)}')
                win_text.tag_configure('hint', foreground='red', background='yellow')

        self.tk.bind("<Key>", self.check_hint_key)

        self.tk.mainloop()

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
        from hintStrings func in https://github.com/philc/vimium/blob/master/content_scripts/link_hints.js
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

        return list(map(lambda s: s[::-1], sorted(hints)))

    def get_visible_workspaces(self):
        visible_workspace_names = [output.current_workspace for output in self.i3.get_outputs()
                                   if output.current_workspace]

        # visible_workspace_ids = [workspace.id for workspace in self.i3.get_workspaces()
        #                          if workspace.visible]

        visible_workspaces = [workspace for workspace in self.i3.get_tree().workspaces()
                              if workspace.name in visible_workspace_names]
        return visible_workspaces

    def get_container_visibility(self, container):
        '''Check the visibility of a container
        from con_is_hidden function in https://github.com/i3/i3/blob/master/src/con.c
        '''
        current = container

        while current != None and current.type != 'workspace':
            parent = current.parent

            if (parent != None and (parent.layout == 'tabbed' or parent.layout == 'stacked')) :
                if (next(iter(parent.focus), None) != current.id):
                    return False

            current = parent

        return True

    def get_hint_trie(self, hints):
        hint_trie = HintTrie()
        for hint in hints:
            hint_trie.insert(hint)
        return hint_trie

    def check_hint_key(self, event):
        if event.keysym == 'Escape':
            self.keystroke_queue = []
            self.tk.destroy()
        elif event.keysym == 'BackSpace':
            self.keystroke_queue = self.keystroke_queue[:-1]
        elif len(event.keysym) == 1:
            self.keystroke_queue.append(event.char)
        else:
            pass

        is_hint = self.hint_trie.match_hint(''.join(self.keystroke_queue))
        if is_hint == 0:
            self.keystroke_queue = []
            self.tk.destroy()
        elif is_hint == 2:
            win_id = self.hint2win[''.join(self.keystroke_queue)]
            self.keystroke_queue = []
            self.tk.destroy()
            win = self.i3.get_tree().find_by_id(win_id)
            win.command('focus')
        else:
            pass


class HintTrie:
    def __init__(self):
        self.children = {}
        self.is_hint = False

    def insert(self, hint):
        node = self

        for ch in hint:
            if ch not in node.children:
                node.children[ch] = HintTrie()
            node = node.children[ch]

        node.is_hint = True

    def match_hint(self, hint):
        node = self

        for ch in hint:
            if ch not in node.children:
                return 0
            node = node.children[ch]

        if node.is_hint:
            return 2
        else:
            return 1


if __name__ == '__main__':
    logger.remove()
    logger.add(os.path.join(SCRIPT_DIR, 'windows.log'))

    title_bar = TitleBar()
    title_bar.launch_i3()

    title_bar.print_title_bar()

    BOSS_KEY = {getattr(keyboard.Key, key) if len(key) > 1 else keyboard.KeyCode(char=key)
                for key in json.loads(title_bar.config.get('general', 'hint-key'))}
    WORKSPACE_KEY = {getattr(keyboard.Key, key) if len(key) > 1 else keyboard.KeyCode(char=key)
                     for key in json.loads(title_bar.config.get('general', 'workspace-hint-key'))}
    pri_keystroke_set = set()

    shift_map = {
        '`': '~', '1': '!', '2': '@', '3': '#', '4': '$', '5': '%', '6': '^', '7': '&',
        '8': '*', '9': '(', '0': ')', '-': '_', '=': '+', 'q': 'Q', 'w': 'W', 'e': 'E',
        'r': 'R', 't': 'T', 'y': 'Y', 'u': 'U', 'i': 'I', 'o': 'O', 'p': 'P', '[': '{',
        ']': '}', '\\': '|', 'a': 'A', 's': 'S', 'd': 'D', 'f': 'F', 'g': 'G', 'h': 'H',
        'j': 'J', 'k': 'K', 'l': 'L', ';': ':', "'": '"', 'z': 'Z', 'x': 'X', 'c': 'C',
        'v': 'V', 'b': 'B', 'n': 'N', 'm': 'M', ',': '<', '.': '>', '/': '?'
    }
    special_shift_key_map = dict(zip([getattr(keyboard.Key, key)
                                      for key in ['tab', 'alt_l', 'alt_r', 'print_screen']],
                                     [pynput.keyboard._xorg.KeyCode(vk=vk)
                                      for vk  in [65056, 65511, 65512, 65301]]))
    special_shift_key_map = {**special_shift_key_map, **{v: k for k, v in special_shift_key_map.items()}}

    with keyboard.Events() as pri_events:
        for pri_event in pri_events:

            if isinstance(pri_event, pynput.keyboard.Events.Press):
                pri_keystroke_set.add(pri_event.key)
                logger.debug(f'Press key {pri_event.key}')
                logger.debug(pri_keystroke_set)

            if len(pri_keystroke_set) and isinstance(pri_event, pynput.keyboard.Events.Release):
                '''
                pri_keystroke_set could be empty in two cases:
                1. when entering the event, no key is pressed
                2. pri key has hit the BOSS_KEY, so it is released in inner events
                In both case, we don't need remove keys from it
                '''
                # If shift-a is pressed, we will record shift and A.
                # If shift is released first, a later,
                # The record is {A, a} or {A} after shift released,
                # due to a is in pressed,
                # release a from record {A} might cause error
                logger.debug(pri_keystroke_set)
                logger.debug(f'Release key {pri_event.key}')
                if isinstance(pri_event.key, pynput.keyboard._xorg.KeyCode):
                    shift_char = shift_map.get(pri_event.key.char, pri_event.key)
                    if pynput.keyboard._xorg.KeyCode(char=shift_char) in pri_keystroke_set:
                        pri_keystroke_set.remove(pynput.keyboard._xorg.KeyCode(char=shift_char))

                if pri_event.key in special_shift_key_map:
                    # Shift 和某些键组合会产生新键
                    # Example case: 新键代码用<>表示
                    #   1. 不需要处理这种情况
                    #      Press Key.Shift, press Key.tab <65056>
                    #      Release Key.tab <65056>, release Key.Shift
                    #   2. 需要处理这种情况
                    #      Press Key.Shift, press Key.tab <65056>
                    #      Release Key.Shift, release Key.tab (65289)
                    #   3. 需要处理这种情况
                    #      Press Key.tab (65289), press Key.Shift
                    #      Release Key.tab <65056>, release Key.Shift
                    #   4. 不需要处理这种情况
                    #      Press Key.tab (65289), press Key.Shift
                    #      Release Key.Shift, release Key.tab (65289)
                    special_key = special_shift_key_map[pri_event.key]
                    if special_key in pri_keystroke_set:
                        pri_keystroke_set.remove(special_key)

                if pri_event.key in pri_keystroke_set:
                    pri_keystroke_set.remove(pri_event.key)

            if pri_keystroke_set == BOSS_KEY:
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

                # Generate hint
                title_bar.print_title_bar(hint=True)
                title_bar.paint_window_hint_on_screen()
            elif pri_keystroke_set == WORKSPACE_KEY:
                # Release boss key
                # Some boss key like ctrl may be hold longer
                with keyboard.Events() as events:
                    for event in events:
                        if event.key in pri_keystroke_set and isinstance(event, pynput.keyboard.Events.Release):
                            pri_keystroke_set.remove(event.key)

                        if len(pri_keystroke_set) == 0:
                            break

                title_bar.paint_workspace_hint_on_screen()
            else:
                title_bar.print_title_bar()
