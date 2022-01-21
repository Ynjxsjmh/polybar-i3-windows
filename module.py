#! /usr/bin/python3

import os
import asyncio
import getpass
import i3ipc
import platform
import configparser

from time import sleep
from string import Template

from icon_resolver import IconResolver

#: Max length of single window title
MAX_LENGTH = 26
#: Base 1 index of the font that should be used for icons
ICON_FONT = 3

HOSTNAME = platform.node()
USER = getpass.getuser()

ICONS = [
    ('class=*.slack.com', '\uf3ef'),

    ('class=Chromium', '\ue743'),
    ('class=Firefox', '\uf738'),
    ('class=URxvt', '\ue795'),
    ('class=Code', '\ue70c'),
    ('class=code-oss-dev', '\ue70c'),

    ('name=mutt', '\uf199'),

    ('*', '\ufaae'),
]

FORMATERS = {
    'Chromium': lambda title: title.replace(' - Chromium', ''),
    'Firefox': lambda title: title.replace(' - Mozilla Firefox', ''),
    'URxvt': lambda title: title.replace('%s@%s: ' % (USER, HOSTNAME), ''),
}

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
COMMAND_PATH = os.path.join(SCRIPT_DIR, 'command.py')

config = configparser.ConfigParser()
config.read(os.path.join(SCRIPT_DIR, 'config.ini'))

icon_resolver = IconResolver(ICONS)


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
    apps = workspace.leaves()
    apps.sort(key=lambda app: app.workspace().name)

    out = f"%{{O{config['title']['interval']}}}".join(format_entry(app) for app in apps)

    print(out, flush=True)


def format_entry(app):
    icon    = make_icon(app)
    title   = make_title(app)
    command = make_command(app)

    title = paint_title(app, icon, title)

    t = Template('%{A1:$left_command:}$title%{A-}')
    entry = t.substitute(left_command=command, title=title)

    return entry


def make_icon(app):
    icon = icon_resolver.resolve({
        'class': app.window_class,
        'name': app.name,
    })

    return Template('%{T$font}$icon%{T-}').substitute(font=ICON_FONT, icon=icon)


def make_title(app):
    klass = app.window_class
    name = app.name

    title = FORMATERS[klass](name) if klass in FORMATERS else name

    if len(title) > MAX_LENGTH:
        title = title[:MAX_LENGTH - 3] + '...'

    return title


def make_command(app):
    left_command = '%s %s' % (COMMAND_PATH, app.id)

    return left_command


def paint_title(app, icon, title):
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


main()
