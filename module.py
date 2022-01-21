#! /usr/bin/python3

import os
import asyncio
import getpass
import i3ipc
import platform

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

    out = '%{O12}'.join(format_entry(app) for app in apps)

    print(out, flush=True)


def format_entry(app):
    icon    = make_icon(app)
    title   = make_title(app)
    command = make_command(app)

    title_ = icon + title
    if app.focused:
        title_ = '%{F#fff}' + title_ + '%{F-}'

    t = Template('%{A1:$left_command:} $title %{A-}')
    entry = t.substitute(left_command=command, title=title_)

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


main()
