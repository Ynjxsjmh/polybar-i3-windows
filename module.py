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

    # Ensure first level nodes only contain the tabbed container
    tabbed_con = workspace.nodes[0]

    titlebar = f"%{{O{config['title']['interval']}}}".join(format_entry(node) for node in tabbed_con.nodes)

    print(titlebar, flush=True)


def format_entry(node):
    if len(node.nodes):
        entry = format_con(node)
    else:
        entry = format_win(node)

    return entry


def format_con(con):
    title = get_con_title(con)

    return title


def format_win(app):
    icon    = make_icon(app)
    title   = make_title(app)
    command = make_command(app)

    title = paint_title(app, icon, title)

    t = Template('%{A1:$left_command:}%{A4:$scroll_up_command:}%{A5:$scroll_down_command:}$title%{A-}%{A-}%{A-}')
    entry = t.substitute(left_command=command['left'],
                         scroll_up_command=command['scroll_up'],
                         scroll_down_command=command['scroll_down'],
                         title=title)

    return entry


def make_icon(app):
    # clear unsupported character in key
    regex = "[\. ]"
    window_class = re.sub(regex, '', app.window_class)
    window_class = window_class.lower()

    icon = config['icon'].get(window_class, '')

    return Template('%{T$font}$icon%{T-}').substitute(font=config['general']['icon-font'], icon=icon)


def make_title(app):
    window_class = app.window_class
    window_title = app.window_title

    workspace = app.workspace()
    window_num = len(workspace.leaves())
    window_len = config['general'].getint('length') // window_num

    title = ''
    if config['title'].getint('title') == 1:
        title = window_class
    else:
        title = window_title

    if len(title) > window_len:
        title = title[:window_len - 3] + '...'

    return title


def make_command(app):
    left_command = '%s %s' % (COMMAND_PATH, app.id)
    scroll_up_command = '%s %s' % (SCROLL_COMMAND_PATH, 1)
    scroll_down_command = '%s %s' % (SCROLL_COMMAND_PATH, 2)

    command = {
        'left': left_command,
        'scroll_up': scroll_up_command,
        'scroll_down': scroll_down_command,
    }

    return command


def paint_title(app, icon, title, nested=False):
    isIcon = config['title'].getboolean('icon')
    isTitle = config['title'].getint('title') > 0
    underline = config['title'].getint('underline')

    ucolor = config['color']['focused-window-underline-color'] if app.focused \
        else config['color']['urgent-window-underline-color'] if app.urgent  \
        else config['color']['window-underline-color']
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

    fcolor = config['color']['focused-window-front-color'] if app.focused \
        else config['color']['urgent-window-front-color'] if app.urgent  \
        else config['color']['window-front-color']
    title = Template('%{F$color}$title%{F-}').substitute(color=fcolor, title=title)

    bcolor = config['color']['focused-window-background-color'] if app.focused \
        else config['color']['urgent-window-background-color'] if app.urgent  \
        else config['color']['window-background-color']
    title = Template('%{B$color}$title%{B-}').substitute(color=bcolor, title=title)

    return title


def get_con_title(node):
    if len(node.nodes):
        title = ' '.join(get_con_title(n) for n in node.nodes)
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
        return format_win(node)


main()
