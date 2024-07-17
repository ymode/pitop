import urwid
import psutil
import datetime
import os
import sys
import logging
import getpass
import argparse
from .web_server import run_server

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

# Global variables
last_bytes_sent = 0
last_bytes_recv = 0
horizontal_line = urwid.Divider(div_char='⏤')
disk_info_text = urwid.Text("") 
need_refresh = False

logging.basicConfig(filename='pitop_debug.log', level=logging.DEBUG)

class ProcessRow(urwid.WidgetWrap):
    def __init__(self, proc_info):
        self.proc_info = proc_info
        self.pid = proc_info['pid']
        name = proc_info['name'][:23]
        cpu = f"{proc_info['cpu_percent']:.1f}" if proc_info['cpu_percent'] is not None else "N/A"
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

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


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
    if key in ('q', 'Q'):
        raise urwid.ExitMainLoop()
    elif key in ('k', 'K'):
        kill_selected_process()
    elif key == 'up':
        process_list.keypress((0,), 'up')
    elif key == 'down':
        process_list.keypress((0,), 'down')


def get_process_list(max_processes=10):
    process_list = []
    active_users = get_usernames().split(", ")
    logging.debug(f"Active users: {active_users}")
    
    include_all = len(active_users) == 0 or (len(active_users) == 1 and active_users[0] == '')
    
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
        try:
            proc_info = {
                'pid': proc.info['pid'],
                'name': proc.info['name'],
                'cpu_percent': proc.info['cpu_percent'],
                'memory_percent': proc.info['memory_percent'],
                'username': proc.info['username']
            }
            if include_all or proc_info['username'] in active_users:
                process_list.append(ProcessRow(proc_info))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logging.debug(f"Error processing a process: {str(e)}")
        except Exception as e:
            logging.debug(f"Unexpected error processing a process: {str(e)}")
    
    logging.debug(f"Number of processes before sorting: {len(process_list)}")
    
    sorted_process_widgets = sorted(
        process_list,
        key=lambda x: x.proc_info['memory_percent'] if x.proc_info['memory_percent'] is not None else 0,
        reverse=True
    )
    limited_process_widgets = sorted_process_widgets[:max_processes]
    
    logging.debug(f"Number of processes after limiting: {len(limited_process_widgets)}")
    
    return limited_process_widgets
def get_disk_info():
    """
    Retrieve information about mounted disks.

    :return: A list of strings with disk information.
    """
    disk_info = []
    for partition in psutil.disk_partitions(all=False):
        if os.name == 'nt':
            if 'cdrom' in partition.opts or partition.fstype == '':
                # skip cd-rom drives with no disk in it on Windows
                continue
        usage = psutil.disk_usage(partition.mountpoint)
        disk_info.append(f"{partition.device} ({partition.mountpoint}): "
                         f"{usage.used / (1024 * 1024 * 1024):.1f}GB / "
                         f"{usage.total / (1024 * 1024 * 1024):.1f}GB "
                         f"({usage.percent}%)")
    return disk_info

def create_progress_bar(percent, width=20):
    filled = int(width * percent / 100)
    empty = width - filled
    bar = '█' * filled + '░' * empty
    return f"[{bar}] {percent:.1f}%"

def create_cpu_progress_bar():
    cpu_percent = psutil.cpu_percent()
    return f"CPU Usage: {create_progress_bar(cpu_percent)}"

def create_ram_progress_bar():
    ram = psutil.virtual_memory()
    return f"RAM Usage: {create_progress_bar(ram.percent)}"

def get_uptime():
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    now = datetime.datetime.now()
    uptime_seconds = (now - boot_time).total_seconds()
    hours, remainder = divmod(int(uptime_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:04d}:{minutes:02d}:{seconds:02d}"

# Function to get hours since boot
def get_hours_since_boot():
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    now = datetime.datetime.now()
    return int((now - boot_time).total_seconds() // 3600)

def get_usernames():
    users = psutil.users()
    usernames = [user.name for user in users]
    if not usernames:
        # If no users are returned, add the current user
        current_user = getpass.getuser()
        usernames.append(current_user)
    unique_usernames = list(set(usernames))
    logging.debug(f"Unique usernames: {unique_usernames}")
    return ', '.join(unique_usernames)

def get_network_info():
    """
    Retrieve current network information.

    :return: A string with network info.
    """
    global last_bytes_sent, last_bytes_recv
    net_io = psutil.net_io_counters()
    bytes_sent = net_io.bytes_sent - last_bytes_sent
    bytes_recv = net_io.bytes_recv - last_bytes_recv
    last_bytes_sent = net_io.bytes_sent
    last_bytes_recv = net_io.bytes_recv
    return f"⬆️ {bytes_sent / 1024:.2f} KB, ⬇️ {bytes_recv / 1024:.2f} KB"

def get_battery_info():
    battery = psutil.sensors_battery()
    if battery:
        percent = f"{battery.percent}%"
        if battery.power_plugged:
            return f"⚡ {percent}"
        else:
            return f"🔋 {percent}"
    else:
        return "⚡ Plugged In"

def kill_selected_process():
    focus = process_list.focus
    if focus is not None:
        pid = focus.pid
        try:
            process = psutil.Process(pid)
            process.terminate()
            logging.debug(f"Process with PID {pid} terminated.")
        except psutil.NoSuchProcess:
            logging.debug(f"No process found with PID {pid}")
        except psutil.AccessDenied:
            logging.debug(f"Access denied when trying to terminate process with PID {pid}")
        # Instead of calling refresh_process_list_callback directly, we'll set a flag
        global need_refresh
        need_refresh = True

def update_system_info(loop, user_data):
    """
    Update system information and refresh the UI.

    :param loop: The main loop object.
    :param user_data: Additional user data.
    """
    cpu_progress_bar_text.set_text(create_cpu_progress_bar())
    ram_progress_bar_text.set_text(create_ram_progress_bar())
    disk_info = get_disk_info()
    disk_info_text.set_text("\n".join(["Disk Usage:"] + disk_info))
    
    # Update footer information
    battery_footer_text.set_text(get_battery_info())
    network_footer_text.set_text(get_network_info())
    footer_text.set_text("Q:Quit")
    
    loop.set_alarm_in(1, update_system_info)


def refresh_process_list_callback(loop, user_data):
    global need_refresh
    try:
        if need_refresh:
            new_process_list = get_process_list(max_processes=10)
            if new_process_list:
                del process_items[:]
                process_items.extend(new_process_list)
                logging.debug(f"Process list updated with {len(new_process_list)} items")
            else:
                logging.debug("get_process_list returned an empty list")
            loop.draw_screen()  # Force a redraw of the screen
            need_refresh = False
        else:
            # Perform regular update
            new_process_list = get_process_list(max_processes=10)
            if new_process_list:
                del process_items[:]
                process_items.extend(new_process_list)
                logging.debug(f"Process list updated with {len(new_process_list)} items")
            else:
                logging.debug("get_process_list returned an empty list")
            loop.draw_screen()  # Force a redraw of the screen
    except Exception as e:
        logging.debug(f"Error in refresh_process_list_callback: {str(e)}")
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
ram_progress_bar_text = urwid.Text(create_ram_progress_bar(), align='right')

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
# Footer
battery_footer_text = urwid.Text("", align='left')
network_footer_text = urwid.Text("", align='center')
footer_text = urwid.Text("Q:Quit  K:Kill Process", align='right')

footer_bar = urwid.AttrMap(urwid.Columns([
    ('weight', 1, battery_footer_text),
    ('weight', 1, network_footer_text),
    ('weight', 1, footer_text)
], dividechars=1), 'footer')

body_content = urwid.Pile([
    ('pack', progress_bars),
    ('pack', urwid.AttrMap(column_headers, 'header')),
    process_list,
    ('pack', horizontal_line),
    ('pack', disk_info_text), 
    ('weight', 1, urwid.Filler(urwid.Divider(), 'top')),
])

frame = urwid.Frame(header=title_bar, body=body_content, footer=footer_bar)


def main(testing=False):
    """
    Main function to run the Pitop application.

    :param testing: Boolean flag for testing mode.
    """
    global process_list
    if testing:
        return True
    else:
        palette = load_palette_config()
        process_items = urwid.SimpleFocusListWalker(get_process_list(max_processes=10))
        process_list = urwid.ListBox(process_items)
        
        # Initialize the process list
        initial_process_list = get_process_list(max_processes=10)
        process_items[:] = initial_process_list
        
        loop = urwid.MainLoop(frame, palette=palette, unhandled_input=handle_input)
        loop.set_alarm_in(1, update_system_info)
        loop.set_alarm_in(30, refresh_process_list_callback)
        loop.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pitop System Monitor")
    parser.add_argument("--web", action="store_true", help="Run web server instead of TUI")
    args = parser.parse_args()

    if args.web:
        run_server()
    else:
        main()
