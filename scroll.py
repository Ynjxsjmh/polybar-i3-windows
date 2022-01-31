#! /usr/bin/python3

import sys
import i3ipc

direction = int(sys.argv[1])
scroll_type = int(sys.argv[2])

i3 = i3ipc.Connection()

tree = i3.get_tree()
focused_app = tree.find_focused()

if scroll_type == 0:
    focused_app.command('focus')
elif scroll_type == 1:
    if direction == 1:
        focused_app.command('focus left')
    elif direction == 2:
        focused_app.command('focus right')
else:
    workspace = focused_app.workspace()
    apps = workspace.leaves()

    idx = apps.index(focused_app)

    if direction == 1:
        idx = 0 if idx <= 0 else idx-1
    elif direction == 2:
        idx = len(apps-1) if idx >= len(apps) else idx+1

    selected_app = apps[idx]
    selected_app.command('focus')
