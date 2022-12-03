#! /usr/bin/python3

import os
import re
import asyncio
import i3ipc
import configparser

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


def main():
    i3 = i3ipc.Connection()

    i3.on('workspace::focus', on_change)
    i3.on('window::focus', on_change)
    i3.on('window', on_change)

    loop = asyncio.get_event_loop()

    loop.run_in_executor(None, i3.main)

    render_apps(i3)

    loop.run_forever()


def on_change(i3, e):
    render_apps(i3)


def render_apps(i3):
    tree = i3.get_tree()
    # Get current workspace
    focused = tree.find_focused()
    workspace = focused.workspace()

    entries = []
    if len(workspace.nodes) == 1 and workspace.nodes[0].layout == 'tabbed':
        # Ensure first level nodes only contain the tabbed container
        tabbed_con = workspace.nodes[0]
        entries = [ format_entry(node) for node in tabbed_con.nodes ]
    else:
        entries = [ format_entry(node) for node in workspace.nodes ]

    interval = "%{O"f"{config['title'].getint('interval', 12)}""}"
    titlebar = interval.join(entries)

    if not titlebar:
        titlebar = interval

    print(titlebar, flush=True)


def format_entry(node):
    if len(node.nodes):
        entry = format_con(node)
    else:
        entry = format_win(node)

    return entry


def format_con(con):
    title = make_con_title(con)

    return title


def format_win(app, nested=False):
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
    isNum = config['title'].getint('number', 0)

    if isNum:
        return title

    apps = []
    get_leaf_nodes(app.workspace(), apps)
    num = apps.index(app) + 1

    hints = get_hint_strings(len(apps))
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


def get_hint_strings(link_count):
    '''
    Returns a list of hint strings which will uniquely identify
    the given number of links. The hint strings may be of different lengths.
    from https://github.com/philc/vimium/blob/master/content_scripts/link_hints.js
    '''
    hint_chars = config['title'].get('hints', 'sadfjklewcmpgh')
    hints = [""];
    offset = 0

    while (((len(hints) - offset) < link_count) or (len(hints) == 1)):
      hint = hints[offset]
      offset += 1
      for ch in hint_chars:
          hints.append(ch + hint)

    hints = hints[offset:offset+link_count]

    return sorted(hints)


def make_con_title(node):
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
        return format_win(node, nested=True)


main()
