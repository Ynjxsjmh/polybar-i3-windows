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

config = configparser.ConfigParser()
config.read(os.path.join(SCRIPT_DIR, 'config.ini'))

default_sections = ['general', 'icon', 'color', 'title']
for section in default_sections:
    if not config.has_section(section):
        config.add_section(section)

hint2win = dict()


def on_change(i3, e):
    render_apps(i3)


def render_apps(i3, hint=False):
    tree = i3.get_tree()
    # Get current workspace
    focused = tree.find_focused()
    workspace = focused.workspace()

    entries = []
    if len(workspace.nodes) == 1 and workspace.nodes[0].layout == 'tabbed':
        # Ensure first level nodes only contain the tabbed container
        tabbed_con = workspace.nodes[0]
        entries = [ format_entry(node, hint=hint) for node in tabbed_con.nodes ]
    else:
        entries = [ format_entry(node, hint=hint) for node in workspace.nodes ]

    interval = "%{O"f"{config['title'].getint('interval', 12)}""}"
    titlebar = interval.join(entries)

    if not titlebar:
        titlebar = interval

    print(titlebar, flush=True)
    return titlebar


def format_entry(node, hint=False):
    if len(node.nodes):
        entry = format_con(node, hint=hint)
    else:
        entry = format_win(node, hint=hint)

    return entry


def format_con(con, hint=False):
    title = make_con_title(con, hint=False)

    return title


def format_win(app, nested=False, hint=False):
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

    title   = make_title(app, nested=nested)
    command = make_command(app)

    title = paint_window_icon(app, title)
    title = paint_window_num(app, title)

    if hint:
        title = paint_window_hint(app, title)

    t = Template('%{A1:$left_command:}%{A4:$scroll_up_command:}%{A5:$scroll_down_command:}$title%{A}%{A}%{A}')
    entry = t.substitute(left_command=command['left'],
                         scroll_up_command=command['scroll_up'],
                         scroll_down_command=command['scroll_down'],
                         title=title)

    return entry


def make_icon(app):
    # The icon is defined in the config file by the window class.
    # We need to clear unsupported character in window class
    # because window class should satisfy the key syntax of INI style.
    regex = "[\. ]"
    window_class = app.window_class if app.window_class \
        else app.window_instance if app.window_instance \
        else ''
    window_class = re.sub(regex, '', window_class)
    window_class = window_class.lower()

    icon = config['icon'].get(window_class, '')
    font = config['general'].getint('icon-font', 0)

    if font:
        return Template('%{T$font}$icon%{T-}').substitute(font=font, icon=icon)
    else:
        return icon


def make_title(app, nested=False):
    window_class = app.window_class if app.window_class \
        else app.window_instance if app.window_instance \
        else ''
    window_title = app.window_title if app.window_title \
        else app.name if app.name \
        else ''

    title = ''
    title_type = 1 if nested else config['title'].getint('title', 2)

    if title_type == 1:
        title = window_class
    else:
        title = window_title

    window_num = len(app.workspace().leaves())
    # consider space between windows
    window_len = config['general'].getint('length', 100) // window_num - 1

    # 47 letters equals to 33 
    # we treat 1  as 2 letters for more flexible
    # as we have symbols like H, V, [, ]
    if window_len >= 3:
        if len(title) > window_len:
            title = title[:window_len - 2] + ''
    else:
        title = title[:1] + '•'

    return title


def make_command(app):
    scroll_type = config['general'].getint('scroll', 2)

    left_command = '%s %s' % (COMMAND_PATH, app.id)
    scroll_up_command = '%s %s %s' % (SCROLL_COMMAND_PATH, 1, scroll_type)
    scroll_down_command = '%s %s %s' % (SCROLL_COMMAND_PATH, 2, scroll_type)

    command = {
        'left': left_command,
        'scroll_up': scroll_up_command,
        'scroll_down': scroll_down_command,
    }

    return command


def paint_window_icon(app, title):
    icon = make_icon(app)

    isIcon = config['title'].getboolean('icon', False)
    isTitle = config['title'].getint('title', 2) > 0
    underline = config['title'].getint('underline', 0)

    ucolor = config['color'].get('focused-window-underline-color', '#b4619a') if app.focused \
        else config['color'].get('urgent-window-underline-color',  '#e84f4f') if app.urgent  \
        else config['color'].get('window-underline-color', '#404040')
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

    fcolor = config['color'].get('focused-window-foreground-color', '#ffffff') if app.focused \
        else config['color'].get('urgent-window-foreground-color',  '#e84f4f') if app.urgent  \
        else config['color'].get('window-foreground-color', '#404040')
    title = Template('%{F$color}$title%{F-}').substitute(color=fcolor, title=title)

    bcolor = config['color'].get('focused-window-background-color', '#000000') if app.focused \
        else config['color'].get('urgent-window-background-color',  '#000000') if app.urgent  \
        else config['color'].get('window-background-color', '#000000')
    title = Template('%{B$color}$title%{B-}').substitute(color=bcolor, title=title)

    return title


def paint_window_num(app, title):
    apps = []
    get_leaf_nodes(app.workspace(), apps)
    num = apps.index(app) + 1

    isNum = config['title'].getint('number', 0)
    isUnderline = config['title'].getboolean('underline-number', False)

    if not isNum:
        return title

    ucolor = config['color'].get('focused-window-number-underline-color', '#b4619a') if app.focused \
        else config['color'].get('urgent-window-number-underline-color',  '#e84f4f') if app.urgent  \
        else config['color'].get('window-number-underline-color', '#404040')
    if isUnderline:
        num = Template('%{+u}%{U$color}$num%{-u}').substitute(color=ucolor, num=num)

    fcolor = config['color'].get('focused-window-number-foreground-color', '#ffffff') if app.focused \
        else config['color'].get('urgent-window-number-foreground-color',  '#e84f4f') if app.urgent  \
        else config['color'].get('window-number-foreground-color', '#404040')
    num = Template('%{F$color}$num%{F-}').substitute(color=fcolor, num=num)

    bcolor = config['color'].get('focused-window-number-background-color', '#000000') if app.focused \
        else config['color'].get('urgent-window-number-background-color',  '#000000') if app.urgent  \
        else config['color'].get('window-number-background-color', '#000000')
    num = Template('%{B$color}$num%{B-}').substitute(color=bcolor, num=num)

    return num + title


def paint_window_hint(app, title):
    global hint2win
    isNum = config['title'].getint('number', 0)

    if isNum:
        return title

    apps = []
    get_leaf_nodes(app.workspace(), apps)
    num = apps.index(app) + 1

    hints = get_hint_strings(len(apps))
    hint2win = dict(zip(hints, apps))
    hint = hints[num - 1]

    fcolor = config['color'].get('focused-window-hint-foreground-color', '#ffffff') if app.focused \
        else config['color'].get('urgent-window-hint-foreground-color',  '#e84f4f') if app.urgent  \
        else config['color'].get('window-hint-foreground-color', '#268bd2')
    hint = Template('%{F$color}$hint%{F-}').substitute(color=fcolor, hint=hint)

    bcolor = config['color'].get('focused-window-hint-background-color', '#00000000') if app.focused \
        else config['color'].get('urgent-window-hint-background-color',  '#00000000') if app.urgent  \
        else config['color'].get('window-hint-background-color', '#00000000')
    hint = Template('%{B$color}$hint%{B-}').substitute(color=bcolor, hint=hint)

    return hint + title


def get_leaf_nodes(node, leafs):
    '''Get window objects under a container

    Parameters
    ----------
    node: i3ipc.con.Con
        A container or workspace that contains many sub-containers or windows.
    leafs: list
        All windows in the target container.

    Returns
    -------
        The function edit leafs variable in-place.
    '''

    if len(node.nodes) == 0:
        leafs.append(node)

    for n in node.nodes:
        get_leaf_nodes(n, leafs)


def get_hint_strings(win_count):
    '''
    Returns a list of hint strings which will uniquely identify
    the given number of links. The hint strings may be of different lengths.
    from https://github.com/philc/vimium/blob/master/content_scripts/link_hints.js
    '''
    hint_chars = config['title'].get('hints', 'sadfjklewcmpgh')
    hints = [""];
    offset = 0

    while (((len(hints) - offset) < win_count) or (len(hints) == 1)):
      hint = hints[offset]
      offset += 1
      for ch in hint_chars:
          hints.append(ch + hint)

    hints = hints[offset:offset+win_count]

    return sorted(hints)


def make_con_title(node, hint=False):
    if len(node.nodes):
        title = ' '.join(make_con_title(n) for n in node.nodes)
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
        return format_win(node, nested=True, hint=hint)


if __name__ == '__main__':

    i3 = i3ipc.Connection()

    i3.on('workspace::focus', on_change)
    i3.on('window::focus', on_change)
    i3.on('window', on_change)

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
                render_apps(i3, hint=True)
                hints = hint2win.keys()
                print(hint2win)

                # Release boss key
                # Some boss key like ctrl may be hold longer
                with keyboard.Events() as events:
                    for event in events:
                        print(event)
                        # 在 release 期间，可能没有释放完全部 boss key，
                        # 而是按其他的键，此时释放的键会出现不在 boss key
                        # 即记录之前按的键（pri_keystroke_set）的中
                        if event.key in pri_keystroke_set and isinstance(event, pynput.keyboard.Events.Release):
                            pri_keystroke_set.remove(event.key)

                        if len(pri_keystroke_set) == 0:
                            break

                # Type hint
                is_quit = 0
                sec_keystroke_queue = []
                with keyboard.Events() as sec_events:
                    for sec_event in sec_events:
                        print(type(sec_event.key))
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

                if not is_quit:
                    # Jump to window
                    render_apps(i3)
                    win = hint2win[''.join(sec_keystroke_queue)]
                    win.command('focus')
            else:
                render_apps(i3)
