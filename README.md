# Polybar i3 windows script

Miss windows-like list of all windows in your taskbar?

<img src="https://user-images.githubusercontent.com/9664601/56872872-05365f00-6a2e-11e9-8383-1849e5980b48.png">

This script is an enhancement version of [meelkor/polybar-i3-windows](https://github.com/meelkor/polybar-i3-windows).

## Features

- [x] Focus window with left mouse button click
- [x] Scroll through window with mouse wheel
- [x] Highlight urgent window
- [x] Showing split info in title for horizontal and vertical layout
- [x] Highly customizable styles for window title

Due to lack of mouse hover support by [lemonbar tags](https://github.com/LemonBoy/bar#formatting), there is no mouse hover action.

## Usage

This script currently only supports tabbed layout. It couldn't ensure the behavior under stacked layout and nested tabbed/stacked layout. Due to [lack of split event](https://github.com/i3/i3/issues/3542) of i3 RPC api, it doesn't ensure real-time display of window split change.

Follow under steps to use it with your polybar

1. Make sure you install `i3ipc` with pip or any other tools
2. Clone this repo to somewhere, for example to `~/.config/polybar/scripts`
3. **Make all scripts executable** with `chmod +x ~/.config/polybar/scripts/polybar-i3-windows`
4. Change any setting you wish in `config.ini`
5. Add the following module to your polybar config:
```ini
[module/i3-windows]
type = custom/script
exec = ~/.config/polybar/scripts/polybar-i3-windows/module.py
tail = true
```

6. Add the module to one of your bars, and don't forget to set a line-size if you intend to use underline, for example like so:
```ini
[bar/your_bar_name]
modules-center = i3-windows
line-size = 2
```

## Configuration

Configuration file should be placed at the same level of `module.py`and its name should be `config.ini`.

You are highly recommended to edit colors under `color` section to suit your polybar theme.

You need to define a UTF8 support font in polybar setting to display all characters in title bar. This script uses `font-2` for icons in the default setting. You probably want it to have higher size than your regular font. Example:

```ini
font-0 = NotoSans Nerd Font:size=10;2
font-1 = siji:pixelsize=16;1
font-2 = NotoSans Nerd Font:size=16;4
```

Variables under `icon` section expect keys to be the **lower case** of window class. If it contains some characters that [`configparser`](https://docs.python.org/3/library/configparser.html) don't support, you should replace it manually by modifying `regex` variable in `make_icon` method. You can use following script to check window class:

```python
import i3ipc

i3 = i3ipc.Connection()
tree = i3.get_tree()

for window in tree.leaves():
    print(window.window_class)
```

Variables under `title` section expect values 

- `interval`: integer value. The interval among window titles.
- `icon`: boolean value, True/False. Whether adding icon at the front of window title.
- `title`: integer value, 0/1/2
  - 0: don't display window title
  - 1: only display window class
  - 2: display window title normally
- `underline`: integer value, 0/1/2/3
  - 0: disable underline feature
  - 1: only underline window title
  - 2: only underline window icon
  - 3: underline both window icon and title
