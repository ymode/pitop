import urwid
import psutil
import datetime
import os
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

# Global variables
last_bytes_sent = 0
last_bytes_recv = 0
horizontal_line = urwid.Divider(div_char='⏤')

class ProcessRow(urwid.WidgetWrap):
    """
    A class to represent a row in the process list.
    """

    def __init__(self, proc_info):
        self.proc_info = proc_info
        self.pid = proc_info['pid']
        name = proc_info['name'][:23]

        # Handle the case where cpu_percent is None
        cpu_percent = proc_info.get('cpu_percent')
        cpu = f"{cpu_percent:.1f}" if cpu_percent is not None else "N/A"
        
        mem = f"{proc_info['memory_percent']:.2f}"
        user = proc_info['username'][:15]

        self.cols = urwid.Columns([
            ('fixed', 25, urwid.Text(name)),
            ('fixed', 15, urwid.Text(user)),
            ('fixed', 8, urwid.Text(str(self.pid))),
            ('fixed', 8, urwid.Text(cpu)),
            ('fixed', 8, urwid.Text(mem))
        ])
        super().__init__(urwid.AttrMap(self.cols, 'normal', focus_map='highlighted'))


def load_palette_config(path="pitop.toml"):
    """
    Load the color palette configuration from a TOML file.

    :param path: Path to the TOML file.
    :return: A list of palette configurations.
    """
    try:
        with open(path, 'rb') as f:
            config = tomllib.load(f)
    except (FileNotFoundError, tomllib.TOMLDecodeError) as e:
        print(f"Error loading configuration file: {e}")
        return []

    palette = [
        ('header', config['palette']['header_fg'], config['palette']['header_bg']),
        ('footer', config['palette']['footer_fg'], config['palette']['footer_bg']),
        ('highlighted', config['palette']['highlighted_fg'], config['palette']['highlighted_bg']),
    ]

    return palette


def handle_input(key):
    """
    Handle keyboard input for the TUI.

    :param key: The key pressed.
    """
    if key in ('q', 'Q'):
        raise urwid.ExitMainLoop()
    elif key in ('k', 'K'):
        pass  # kill_selected_process()
    elif key == 'up':
        pass  # Scroll up
    elif key == 'down':
        pass  # Scroll down


def get_process_list(max_processes=10):
    """
    Retrieve a list of processes to display.

    :param max_processes: Maximum number of processes to display.
    :return: A list of ProcessRow widgets.
    """
    process_list = []
    for proc in psutil.process_iter(attrs=['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
        try:
            process_info = proc.info
            process_list.append(ProcessRow(process_info))
            if len(process_list) >= max_processes:
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return process_list


def create_cpu_progress_bar():
    """
    Create a progress bar for CPU usage.

    :return: A string representation of the CPU progress bar.
    """
    cpu_percent = psutil.cpu_percent()
    return f"CPU Usage: [{'#' * int(cpu_percent / 10)}{'.' * (10 - int(cpu_percent / 10))}] {cpu_percent}%"


def create_ram_progress_bar():
    """
    Create a progress bar for RAM usage.

    :return: A string representation of the RAM progress bar.
    """
    ram = psutil.virtual_memory()
    ram_percent = ram.percent
    return f"RAM Usage: [{'#' * int(ram_percent / 10)}{'.' * (10 - int(ram_percent / 10))}] {ram_percent}%"


def get_network_info():
    """
    Retrieve current network information.

    :return: A tuple with network info strings.
    """
    global last_bytes_sent, last_bytes_recv
    net_io = psutil.net_io_counters()
    bytes_sent = net_io.bytes_sent - last_bytes_sent
    bytes_recv = net_io.bytes_recv - last_bytes_recv
    last_bytes_sent = net_io.bytes_sent
    last_bytes_recv = net_io.bytes_recv
    return (f"Sent: {bytes_sent / 1024:.2f} KB", f"Recv: {bytes_recv / 1024:.2f} KB")


def update_system_info(loop, user_data):
    """
    Update system information and refresh the UI.

    :param loop: The main loop object.
    :param user_data: Additional user data.
    """
    cpu_progress_bar_text.set_text(create_cpu_progress_bar())
    ram_progress_bar_text.set_text(create_ram_progress_bar())
    loop.set_alarm_in(1, update_system_info)


def refresh_process_list_callback(loop, user_data):
    """
    Refresh the process list.

    :param loop: The main loop object.
    :param user_data: Additional user data.
    """
    process_items[:] = get_process_list(max_processes=10)
    loop.set_alarm_in(30, refresh_process_list_callback)


# Header
title_text = urwid.Text("Pitop", align='left')
uptime_text = urwid.Text(str(datetime.datetime.now()), align='center')
cpu_text = urwid.Text("CPU", align='right')

title_bar = urwid.AttrMap(urwid.Columns([
    ('weight', 0.70, title_text),
    ('weight', 0.20, uptime_text),
    ('weight', 0.15, cpu_text)
], dividechars=1), 'header')

# Body
cpu_progress_bar_text = urwid.Text(create_cpu_progress_bar(), align='left')
ram_progress_bar_text = urwid.Text(create_ram_progress_bar(), align='left')

progress_bars = urwid.Columns([
    ('weight', 1, cpu_progress_bar_text),
    ('weight', 1, ram_progress_bar_text)
])

process_items = urwid.SimpleFocusListWalker(get_process_list(max_processes=10))
process_list = urwid.ListBox(process_items)
column_headers = urwid.Columns([
    ('fixed', 25, urwid.Text('Name')),
    ('fixed', 15, urwid.Text('User')),
    ('fixed', 8, urwid.Text('PID')),
    ('fixed', 8, urwid.Text('CPU%')),
    ('fixed', 8, urwid.Text('MEM%'))
])

# Footer
battery_footer_text = urwid.Text("", align='left')
network_footer_text = urwid.Text("", align='center')
network_info_initial = 'Network' + ' '.join(get_network_info())
footer_text = urwid.Text(network_info_initial + " Q:Quit", align='right')

footer_bar = urwid.AttrMap(urwid.Columns([
    ('weight', 1, battery_footer_text),
    ('weight', 1, network_footer_text),
], dividechars=1), 'footer')

body_content = urwid.Pile([
    ('pack', progress_bars),
    ('pack', urwid.AttrMap(column_headers, 'header')),
    process_list,  # This will be as tall as its contents
    ('pack', horizontal_line),
    ('weight', 1, urwid.Filler(urwid.Divider(), 'top')),
])

frame = urwid.Frame(header=title_bar, body=body_content, footer=footer_bar)


def main(testing=False):
    """
    Main function to run the Pitop application.

    :param testing: Boolean flag for testing mode.
    """
    if testing:
        return True
    else:
        palette = load_palette_config()
        loop = urwid.MainLoop(frame, palette=palette, unhandled_input=handle_input)
        loop.set_alarm_in(1, update_system_info)
        loop.set_alarm_in(30, refresh_process_list_callback)

        loop.run()


if __name__ == "__main__":
    main()
